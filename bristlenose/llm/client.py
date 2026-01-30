"""Multi-provider LLM client with structured output support."""

from __future__ import annotations

import json
import logging
from typing import TypeVar

from pydantic import BaseModel

from bristlenose.config import BristlenoseSettings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMClient:
    """Unified interface for LLM calls with Pydantic-validated structured output.

    Supports Anthropic (Claude) and OpenAI as providers.
    """

    def __init__(self, settings: BristlenoseSettings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        self._anthropic_client: object | None = None
        self._openai_client: object | None = None

        # Validate API key is present for the selected provider
        self._validate_api_key()

    def _validate_api_key(self) -> None:
        """Check that the required API key is configured."""
        if self.provider == "anthropic" and not self.settings.anthropic_api_key:
            raise ValueError(
                "Anthropic API key not set. "
                "Set BRISTLENOSE_ANTHROPIC_API_KEY in your .env file or environment. "
                "Looked for .env in: current directory and bristlenose package directory."
            )
        if self.provider == "openai" and not self.settings.openai_api_key:
            raise ValueError(
                "OpenAI API key not set. "
                "Set BRISTLENOSE_OPENAI_API_KEY in your .env file or environment."
            )

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

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Empty response from OpenAI")

        data = json.loads(content)
        return response_model.model_validate(data)
