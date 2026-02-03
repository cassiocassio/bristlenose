"""Multi-provider LLM client with structured output support."""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from pydantic import BaseModel

from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMUsageTracker:
    """Accumulates token usage across multiple LLM calls.

    Safe to share across concurrent asyncio tasks (single-threaded event loop).
    """

    def __init__(self) -> None:
        self.input_tokens: int = 0
        self.output_tokens: int = 0
        self.calls: int = 0

    def record(self, input_tokens: int, output_tokens: int) -> None:
        """Record token usage from a single API call."""
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class LLMClient:
    """Unified interface for LLM calls with Pydantic-validated structured output.

    Supports Claude (Anthropic), ChatGPT (OpenAI), and Local (Ollama) as providers.
    """

    def __init__(self, settings: BristlenoseSettings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        self._anthropic_client: object | None = None
        self._openai_client: object | None = None
        self._local_client: object | None = None
        self.tracker = LLMUsageTracker()

        # Validate API key is present for the selected provider
        self._validate_api_key()

    def _validate_api_key(self) -> None:
        """Check that the required API key is configured (cloud providers only)."""
        if self.provider == "anthropic" and not self.settings.anthropic_api_key:
            raise ValueError(
                "Claude API key not set. "
                "Set BRISTLENOSE_ANTHROPIC_API_KEY in your .env file or environment. "
                "Get a key from console.anthropic.com"
            )
        if self.provider == "openai" and not self.settings.openai_api_key:
            raise ValueError(
                "ChatGPT API key not set. "
                "Set BRISTLENOSE_OPENAI_API_KEY in your .env file or environment. "
                "Get a key from platform.openai.com"
            )
        # Local provider doesn't need an API key

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int | None = None,
    ) -> T:
        """Send a prompt and parse the response into a Pydantic model.

        Args:
            system_prompt: System-level instructions.
            user_prompt: The user prompt with the actual task.
            response_model: Pydantic model class for structured output.
            max_tokens: Override max tokens (defaults to settings.llm_max_tokens).

        Returns:
            An instance of response_model populated from the LLM response.
        """
        max_tokens = max_tokens or self.settings.llm_max_tokens

        if self.provider == "anthropic":
            return await self._analyze_anthropic(
                system_prompt, user_prompt, response_model, max_tokens
            )
        elif self.provider == "openai":
            return await self._analyze_openai(
                system_prompt, user_prompt, response_model, max_tokens
            )
        elif self.provider == "local":
            return await self._analyze_local(
                system_prompt, user_prompt, response_model, max_tokens
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    async def _analyze_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
    ) -> T:
        """Call Anthropic API with tool use for structured output."""
        import anthropic

        if self._anthropic_client is None:
            self._anthropic_client = anthropic.AsyncAnthropic(
                api_key=self.settings.anthropic_api_key,
            )

        client: anthropic.AsyncAnthropic = self._anthropic_client  # type: ignore[assignment]

        # Build a tool definition from the Pydantic schema
        schema = response_model.model_json_schema()
        tool_name = "structured_output"

        tool = {
            "name": tool_name,
            "description": f"Return the analysis result as a {response_model.__name__} object.",
            "input_schema": schema,
        }

        logger.debug("Calling Anthropic API: model=%s", self.settings.llm_model)

        response = await client.messages.create(
            model=self.settings.llm_model,
            max_tokens=max_tokens,
            temperature=self.settings.llm_temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            tools=[tool],
            tool_choice={"type": "tool", "name": tool_name},
        )

        # Track token usage
        if hasattr(response, "usage") and response.usage:
            self.tracker.record(response.usage.input_tokens, response.usage.output_tokens)

        # Extract the tool use result
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return response_model.model_validate(block.input)

        raise RuntimeError("No structured output found in Anthropic response")

    async def _analyze_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
    ) -> T:
        """Call OpenAI API with JSON mode for structured output."""
        import openai

        if self._openai_client is None:
            self._openai_client = openai.AsyncOpenAI(
                api_key=self.settings.openai_api_key,
            )

        client: openai.AsyncOpenAI = self._openai_client  # type: ignore[assignment]

        # Add JSON schema instruction to the system prompt
        schema = response_model.model_json_schema()
        schema_instruction = (
            f"\n\nYou must respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```"
        )

        logger.debug("Calling OpenAI API: model=%s", self.settings.llm_model)

        response = await client.chat.completions.create(
            model=self.settings.llm_model,
            max_tokens=max_tokens,
            temperature=self.settings.llm_temperature,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt + schema_instruction},
                {"role": "user", "content": user_prompt},
            ],
        )

        # Track token usage
        if hasattr(response, "usage") and response.usage:
            self.tracker.record(
                response.usage.prompt_tokens, response.usage.completion_tokens
            )

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Empty response from OpenAI")

        data = json.loads(content)
        return response_model.model_validate(data)

    async def _analyze_local(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
    ) -> T:
        """Call local Ollama-compatible API with JSON mode.

        Uses the OpenAI SDK pointed at a local endpoint. Includes retry logic
        for JSON parsing failures since local models are less reliable (~85%
        schema compliance vs ~99% for cloud models).
        """
        import asyncio

        import openai

        if self._local_client is None:
            self._local_client = openai.AsyncOpenAI(
                base_url=self.settings.local_url,
                api_key="ollama",  # Required by SDK but ignored by Ollama
            )

        client: openai.AsyncOpenAI = self._local_client  # type: ignore[assignment]

        # Add JSON schema instruction to the system prompt
        schema = response_model.model_json_schema()
        schema_instruction = (
            f"\n\nYou must respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```"
        )

        model = self.settings.local_model
        logger.debug("Calling local API: url=%s model=%s", self.settings.local_url, model)

        # Retry logic for JSON parsing failures
        max_retries = 3
        last_error: Exception | None = None

        for attempt in range(max_retries):
            try:
                response = await client.chat.completions.create(
                    model=model,
                    max_tokens=max_tokens,
                    temperature=self.settings.llm_temperature,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt + schema_instruction},
                        {"role": "user", "content": user_prompt},
                    ],
                )

                # Track token usage (Ollama provides this)
                if hasattr(response, "usage") and response.usage:
                    self.tracker.record(
                        response.usage.prompt_tokens or 0,
                        response.usage.completion_tokens or 0,
                    )

                content = response.choices[0].message.content
                if content is None:
                    raise RuntimeError("Empty response from local model")

                data = json.loads(content)
                return response_model.model_validate(data)

            except json.JSONDecodeError as e:
                last_error = e
                logger.debug(
                    "JSON parse failed (attempt %d/%d): %s", attempt + 1, max_retries, e
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Backoff

        raise RuntimeError(
            f"Local model failed to produce valid JSON after {max_retries} attempts. "
            f"Last error: {last_error}. "
            f"Try a larger model (--model llama3.1:8b) or use a cloud API (--llm claude)."
        )
