"""Multi-provider LLM client with structured output support."""

from __future__ import annotations

import asyncio
import copy
import json
import logging
import time
from typing import Literal, TypeVar

from pydantic import BaseModel

from bristlenose.config import BristlenoseSettings
from bristlenose.llm import telemetry
from bristlenose.llm.pricing import PRICE_TABLE_VERSION
from bristlenose.llm.prompts import PromptTemplate

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def _repo_relative_prompt_path(template: PromptTemplate) -> str:
    """Return the prompt file path as a repo-relative string.

    Absolute paths leak the OS username (`/Users/<who>/...`) into the JSONL
    log; the prompts directory is fixed by the package layout, so emit the
    canonical repo-relative form instead.
    """
    return f"bristlenose/llm/prompts/{template.path.name}"


# ---------------------------------------------------------------------------
# Gemini schema helpers
# ---------------------------------------------------------------------------


def _flatten_schema_for_gemini(schema: dict) -> dict:
    """Flatten a Pydantic JSON schema for Gemini's native structured output.

    Gemini's ``response_schema`` may not support JSON Schema ``$ref`` pointers
    or ``anyOf`` unions with null.  This function:

    1. Inlines all ``$defs`` / ``$ref`` references.
    2. Converts ``anyOf``-with-null (``[{"type": "string"}, {"type": "null"}]``)
       to the non-null branch (Gemini returns "" instead of null).
    3. Removes the top-level ``$defs`` key after inlining.
    4. Strips ``title`` keys (Gemini ignores them, but they bloat the schema).

    The returned schema is a deep copy — the original is not modified.
    """
    schema = copy.deepcopy(schema)
    defs = schema.pop("$defs", {})

    def _resolve(node: object) -> object:
        """Recursively resolve $ref pointers and simplify anyOf-with-null."""
        if isinstance(node, dict):
            # Resolve $ref
            if "$ref" in node:
                ref_path: str = node["$ref"]
                # Only handle local #/$defs/Name references
                if ref_path.startswith("#/$defs/"):
                    def_name = ref_path[len("#/$defs/"):]
                    if def_name in defs:
                        return _resolve(copy.deepcopy(defs[def_name]))
                return node  # unresolvable ref — leave as-is

            # Simplify anyOf with null
            if "anyOf" in node:
                variants = node["anyOf"]
                non_null = [v for v in variants if v != {"type": "null"}]
                if len(non_null) == 1 and len(variants) == 2:
                    # anyOf: [{"type": "string"}, {"type": "null"}] → {"type": "string"}
                    merged = {**node}
                    del merged["anyOf"]
                    merged.update(_resolve(non_null[0]))  # type: ignore[arg-type]
                    merged.pop("default", None)  # remove null default
                    return merged

            # Recurse into all dict values
            return {
                k: _resolve(v) for k, v in node.items()
                if k != "title"  # strip title keys
            }

        if isinstance(node, list):
            return [_resolve(item) for item in node]

        return node

    return _resolve(schema)  # type: ignore[return-value]


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

    Supports Claude (Anthropic), ChatGPT (OpenAI), Azure OpenAI, Gemini (Google),
    and Local (Ollama) as providers.
    """

    # Class-level: first telemetry failure per process is logged at WARNING,
    # subsequent failures at DEBUG. Avoids both silent degradation and spam.
    _telemetry_failure_warned: bool = False

    def __init__(self, settings: BristlenoseSettings) -> None:
        self.settings = settings
        self.provider = settings.llm_provider
        self._anthropic_client: object | None = None
        self._openai_client: object | None = None
        self._azure_client: object | None = None
        self._google_client: object | None = None
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
        if self.provider == "azure":
            if not self.settings.azure_endpoint:
                raise ValueError(
                    "Azure OpenAI endpoint not set. "
                    "Set BRISTLENOSE_AZURE_ENDPOINT to your resource URL "
                    "(e.g. https://my-resource.openai.azure.com/)."
                )
            if not self.settings.azure_api_key:
                raise ValueError(
                    "Azure OpenAI API key not set. "
                    "Set BRISTLENOSE_AZURE_API_KEY from your Azure portal."
                )
            if not self.settings.azure_deployment:
                raise ValueError(
                    "Azure OpenAI deployment name not set. "
                    "Set BRISTLENOSE_AZURE_DEPLOYMENT to your model deployment name."
                )
        if self.provider == "google" and not self.settings.google_api_key:
            raise ValueError(
                "Gemini API key not set. "
                "Set BRISTLENOSE_GOOGLE_API_KEY in your .env file or environment. "
                "Get a key from aistudio.google.com/apikey"
            )
        # Local provider doesn't need an API key

    async def analyze(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int | None = None,
        prompt_template: PromptTemplate | None = None,
    ) -> T:
        """Send a prompt and parse the response into a Pydantic model.

        Args:
            system_prompt: System-level instructions.
            user_prompt: The user prompt with the actual task.
            response_model: Pydantic model class for structured output.
            max_tokens: Override max tokens (defaults to settings.llm_max_tokens).
            prompt_template: Optional template carrying id/version/sha for
                telemetry. When None, the JSONL row's prompt fields stay
                null — used by ad-hoc callers without registered prompts.

        Returns:
            An instance of response_model populated from the LLM response.
        """
        max_tokens = max_tokens or self.settings.llm_max_tokens
        input_chars = len(system_prompt) + len(user_prompt)

        t0 = time.perf_counter()
        try:
            try:
                if self.provider == "anthropic":
                    result = await self._analyze_anthropic(
                        system_prompt, user_prompt, response_model, max_tokens,
                        prompt_template, input_chars, t0,
                    )
                elif self.provider == "openai":
                    result = await self._analyze_openai(
                        system_prompt, user_prompt, response_model, max_tokens,
                        prompt_template, input_chars, t0,
                    )
                elif self.provider == "azure":
                    result = await self._analyze_azure(
                        system_prompt, user_prompt, response_model, max_tokens,
                        prompt_template, input_chars, t0,
                    )
                elif self.provider == "google":
                    result = await self._analyze_google(
                        system_prompt, user_prompt, response_model, max_tokens,
                        prompt_template, input_chars, t0,
                    )
                elif self.provider == "local":
                    result = await self._analyze_local(
                        system_prompt, user_prompt, response_model, max_tokens,
                        prompt_template, input_chars, t0,
                    )
                else:
                    raise ValueError(f"Unsupported LLM provider: {self.provider}")
            except asyncio.CancelledError:
                self._record_call(
                    request_model=self._provider_request_model(),
                    response_model=None,
                    input_chars=input_chars,
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                    outcome="cancelled",
                    prompt_template=prompt_template,
                    usage_source="missing",
                )
                raise
        finally:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            # Stable, greppable prefix for perf baselining — see
            # docs/design-perf-fossda-baseline.md step 5.
            logger.info(
                "llm_request | provider=%s | model=%s | elapsed_ms=%d | "
                "schema=%s",
                self.provider,
                self.settings.llm_model,
                elapsed_ms,
                response_model.__name__,
            )
        return result

    def _provider_request_model(self) -> str:
        """Return the per-provider 'request model' string used in telemetry."""
        if self.provider == "azure":
            return self.settings.azure_deployment or ""
        if self.provider == "local":
            return self.settings.local_model
        return self.settings.llm_model

    def _record_call(
        self,
        *,
        request_model: str,
        response_model: str | None,
        input_chars: int,
        elapsed_ms: int,
        outcome: Literal["ok", "truncated", "error", "cancelled"],
        prompt_template: PromptTemplate | None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cache_read_input_tokens: int | None = None,
        cache_creation_input_tokens: int | None = None,
        retry_count: int = 0,
        finish_reason: str | None = None,
        usage_source: Literal["reported", "missing"] = "reported",
    ) -> None:
        """Thin wrapper around ``telemetry.record_call`` — never raises."""
        try:
            telemetry.record_call(
                provider=self.provider,
                request_model=request_model,
                response_model=response_model,
                input_chars=input_chars,
                elapsed_ms=elapsed_ms,
                outcome=outcome,
                price_table_version=PRICE_TABLE_VERSION,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_input_tokens=cache_read_input_tokens,
                cache_creation_input_tokens=cache_creation_input_tokens,
                retry_count=retry_count,
                finish_reason=finish_reason,
                usage_source=usage_source,
                prompt_id=prompt_template.id if prompt_template else None,
                prompt_version=prompt_template.version if prompt_template else None,
                prompt_path=(
                    _repo_relative_prompt_path(prompt_template)
                    if prompt_template else None
                ),
                prompt_sha=prompt_template.sha if prompt_template else None,
            )
        except Exception:
            # Telemetry must never break a real LLM call. First failure per
            # process is logged at WARNING so disk-full / permission /
            # symlink-rejection problems are visible; subsequent failures
            # drop to DEBUG to avoid spamming a long-running session.
            if not LLMClient._telemetry_failure_warned:
                LLMClient._telemetry_failure_warned = True
                logger.warning(
                    "telemetry record_call failed; subsequent failures at DEBUG",
                    exc_info=True,
                )
            else:
                logger.debug("telemetry record_call failed", exc_info=True)

    async def _analyze_anthropic(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
        prompt_template: PromptTemplate | None,
        input_chars: int,
        t0: float,
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

        logger.info("Calling Anthropic API: model=%s", self.settings.llm_model)

        request_model = self.settings.llm_model
        try:
            response = await client.messages.create(
                model=request_model,
                max_tokens=max_tokens,
                temperature=self.settings.llm_temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                # Explicit timeout bypasses the SDK's heuristic that rejects
                # non-streaming requests when max_tokens is high (>~21K).
                timeout=600.0,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_call(
                request_model=request_model,
                response_model=None,
                input_chars=input_chars,
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
                outcome="error",
                prompt_template=prompt_template,
                usage_source="missing",
            )
            raise

        # Track token usage
        input_tokens: int | None = None
        output_tokens: int | None = None
        cache_read: int | None = None
        cache_create: int | None = None
        usage_source: Literal["reported", "missing"] = "missing"
        if hasattr(response, "usage") and response.usage:
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            cache_read = getattr(response.usage, "cache_read_input_tokens", None)
            cache_create = getattr(response.usage, "cache_creation_input_tokens", None)
            usage_source = "reported"
            self.tracker.record(input_tokens, output_tokens)
            logger.info(
                "LLM call: model=%s input_tokens=%d output_tokens=%d",
                self.settings.llm_model,
                input_tokens,
                output_tokens,
            )

        response_model_str = getattr(response, "model", None)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Detect truncated response — the tool use JSON is incomplete
        if response.stop_reason == "max_tokens":
            self._record_call(
                request_model=request_model,
                response_model=response_model_str,
                input_chars=input_chars,
                elapsed_ms=elapsed_ms,
                outcome="truncated",
                prompt_template=prompt_template,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_input_tokens=cache_read,
                cache_creation_input_tokens=cache_create,
                finish_reason="max_tokens",
                usage_source=usage_source,
            )
            raise RuntimeError(
                f"LLM response was truncated (hit max_tokens={max_tokens}). "
                f"Set BRISTLENOSE_LLM_MAX_TOKENS=65536 in your .env file."
            )

        self._record_call(
            request_model=request_model,
            response_model=response_model_str,
            input_chars=input_chars,
            elapsed_ms=elapsed_ms,
            outcome="ok",
            prompt_template=prompt_template,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_input_tokens=cache_read,
            cache_creation_input_tokens=cache_create,
            finish_reason=response.stop_reason,
            usage_source=usage_source,
        )

        # Extract the tool use result
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                logger.debug(
                    "Anthropic tool input fields: %s",
                    {k: type(v).__name__ for k, v in block.input.items()},
                )
                return response_model.model_validate(block.input)

        raise RuntimeError("No structured output found in Anthropic response")

    async def _analyze_openai(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
        prompt_template: PromptTemplate | None,
        input_chars: int,
        t0: float,
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

        logger.info("Calling OpenAI API: model=%s", self.settings.llm_model)

        request_model = self.settings.llm_model
        try:
            response = await client.chat.completions.create(
                model=request_model,
                max_tokens=max_tokens,
                temperature=self.settings.llm_temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt + schema_instruction},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_call(
                request_model=request_model, response_model=None,
                input_chars=input_chars,
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
                outcome="error", prompt_template=prompt_template,
                usage_source="missing",
            )
            raise

        input_tokens: int | None = None
        output_tokens: int | None = None
        usage_source: Literal["reported", "missing"] = "missing"
        if hasattr(response, "usage") and response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            usage_source = "reported"
            self.tracker.record(input_tokens, output_tokens)
            logger.info(
                "LLM call: model=%s input_tokens=%d output_tokens=%d",
                self.settings.llm_model,
                input_tokens,
                output_tokens,
            )

        finish_reason = response.choices[0].finish_reason
        response_model_str = getattr(response, "model", None)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Detect truncated response — the JSON is incomplete
        if finish_reason == "length":
            self._record_call(
                request_model=request_model, response_model=response_model_str,
                input_chars=input_chars, elapsed_ms=elapsed_ms,
                outcome="truncated", prompt_template=prompt_template,
                input_tokens=input_tokens, output_tokens=output_tokens,
                finish_reason=finish_reason, usage_source=usage_source,
            )
            raise RuntimeError(
                f"LLM response was truncated (hit max_tokens={max_tokens}). "
                f"Set BRISTLENOSE_LLM_MAX_TOKENS=65536 in your .env file."
            )

        self._record_call(
            request_model=request_model, response_model=response_model_str,
            input_chars=input_chars, elapsed_ms=elapsed_ms,
            outcome="ok", prompt_template=prompt_template,
            input_tokens=input_tokens, output_tokens=output_tokens,
            finish_reason=finish_reason, usage_source=usage_source,
        )

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Empty response from OpenAI")

        data = json.loads(content)
        logger.debug(
            "LLM response fields: %s",
            {k: type(v).__name__ for k, v in data.items()}
            if isinstance(data, dict)
            else type(data).__name__,
        )
        return response_model.model_validate(data)

    async def _analyze_azure(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
        prompt_template: PromptTemplate | None,
        input_chars: int,
        t0: float,
    ) -> T:
        """Call Azure OpenAI API with JSON mode for structured output."""
        import openai

        if self._azure_client is None:
            self._azure_client = openai.AsyncAzureOpenAI(
                api_key=self.settings.azure_api_key,
                azure_endpoint=self.settings.azure_endpoint,
                api_version=self.settings.azure_api_version,
            )

        client: openai.AsyncAzureOpenAI = self._azure_client  # type: ignore[assignment]

        # Add JSON schema instruction to the system prompt
        schema = response_model.model_json_schema()
        schema_instruction = (
            f"\n\nYou must respond with valid JSON matching this schema:\n"
            f"```json\n{json.dumps(schema, indent=2)}\n```"
        )

        logger.info(
            "Calling Azure OpenAI API: deployment=%s", self.settings.azure_deployment
        )

        request_model = self.settings.azure_deployment or ""
        try:
            response = await client.chat.completions.create(
                model=request_model,
                max_tokens=max_tokens,
                temperature=self.settings.llm_temperature,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt + schema_instruction},
                    {"role": "user", "content": user_prompt},
                ],
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_call(
                request_model=request_model, response_model=None,
                input_chars=input_chars,
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
                outcome="error", prompt_template=prompt_template,
                usage_source="missing",
            )
            raise

        input_tokens: int | None = None
        output_tokens: int | None = None
        usage_source: Literal["reported", "missing"] = "missing"
        if hasattr(response, "usage") and response.usage:
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens
            usage_source = "reported"
            self.tracker.record(input_tokens, output_tokens)
            logger.info(
                "LLM call: deployment=%s input_tokens=%d output_tokens=%d",
                self.settings.azure_deployment,
                input_tokens,
                output_tokens,
            )

        finish_reason = response.choices[0].finish_reason
        response_model_str = getattr(response, "model", None)
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        if finish_reason == "length":
            self._record_call(
                request_model=request_model, response_model=response_model_str,
                input_chars=input_chars, elapsed_ms=elapsed_ms,
                outcome="truncated", prompt_template=prompt_template,
                input_tokens=input_tokens, output_tokens=output_tokens,
                finish_reason=finish_reason, usage_source=usage_source,
            )
            raise RuntimeError(
                f"LLM response was truncated (hit max_tokens={max_tokens}). "
                f"Set BRISTLENOSE_LLM_MAX_TOKENS=65536 in your .env file."
            )

        self._record_call(
            request_model=request_model, response_model=response_model_str,
            input_chars=input_chars, elapsed_ms=elapsed_ms,
            outcome="ok", prompt_template=prompt_template,
            input_tokens=input_tokens, output_tokens=output_tokens,
            finish_reason=finish_reason, usage_source=usage_source,
        )

        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Empty response from Azure OpenAI")

        data = json.loads(content)
        logger.debug(
            "LLM response fields: %s",
            {k: type(v).__name__ for k, v in data.items()}
            if isinstance(data, dict)
            else type(data).__name__,
        )
        return response_model.model_validate(data)

    async def _analyze_google(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
        prompt_template: PromptTemplate | None,
        input_chars: int,
        t0: float,
    ) -> T:
        """Call Google Gemini API with native JSON schema for structured output."""
        from google import genai
        from google.genai import types

        if self._google_client is None:
            self._google_client = genai.Client(
                api_key=self.settings.google_api_key,
            )

        client = self._google_client.aio  # type: ignore[union-attr]

        schema = _flatten_schema_for_gemini(response_model.model_json_schema())

        logger.info("Calling Gemini API: model=%s", self.settings.llm_model)

        request_model = self.settings.llm_model
        try:
            response = await client.models.generate_content(
                model=request_model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    response_schema=schema,
                    max_output_tokens=max_tokens,
                    temperature=self.settings.llm_temperature,
                ),
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            self._record_call(
                request_model=request_model, response_model=None,
                input_chars=input_chars,
                elapsed_ms=int((time.perf_counter() - t0) * 1000),
                outcome="error", prompt_template=prompt_template,
                usage_source="missing",
            )
            raise

        input_tokens: int | None = None
        output_tokens: int | None = None
        usage_source: Literal["reported", "missing"] = "missing"
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            input_tokens = response.usage_metadata.prompt_token_count or 0
            output_tokens = response.usage_metadata.candidates_token_count or 0
            usage_source = "reported"
            self.tracker.record(input_tokens, output_tokens)
            logger.info(
                "LLM call: model=%s input_tokens=%d output_tokens=%d",
                self.settings.llm_model,
                input_tokens,
                output_tokens,
            )

        finish_reason_obj = (
            response.candidates[0].finish_reason
            if response.candidates and response.candidates[0].finish_reason
            else None
        )
        finish_reason = str(finish_reason_obj) if finish_reason_obj else None
        response_model_str = getattr(response, "model_version", None) or request_model
        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Detect truncated response — Gemini uses "MAX_TOKENS" finish reason
        if finish_reason in ("MAX_TOKENS", "2"):
            self._record_call(
                request_model=request_model, response_model=response_model_str,
                input_chars=input_chars, elapsed_ms=elapsed_ms,
                outcome="truncated", prompt_template=prompt_template,
                input_tokens=input_tokens, output_tokens=output_tokens,
                finish_reason=finish_reason, usage_source=usage_source,
            )
            raise RuntimeError(
                f"LLM response was truncated (hit max_tokens={max_tokens}). "
                f"Set BRISTLENOSE_LLM_MAX_TOKENS=65536 in your .env file."
            )

        self._record_call(
            request_model=request_model, response_model=response_model_str,
            input_chars=input_chars, elapsed_ms=elapsed_ms,
            outcome="ok", prompt_template=prompt_template,
            input_tokens=input_tokens, output_tokens=output_tokens,
            finish_reason=finish_reason, usage_source=usage_source,
        )

        if not response.text:
            raise RuntimeError("Empty response from Gemini")

        data = json.loads(response.text)
        logger.debug(
            "LLM response fields: %s",
            {k: type(v).__name__ for k, v in data.items()}
            if isinstance(data, dict)
            else type(data).__name__,
        )
        return response_model.model_validate(data)

    async def _analyze_local(
        self,
        system_prompt: str,
        user_prompt: str,
        response_model: type[T],
        max_tokens: int,
        prompt_template: PromptTemplate | None,
        input_chars: int,
        t0: float,
    ) -> T:
        """Call local Ollama-compatible API with JSON mode.

        Uses the OpenAI SDK pointed at a local endpoint. Includes retry logic
        for JSON parsing failures since local models are less reliable (~85%
        schema compliance vs ~99% for cloud models).
        """

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
        logger.info("Calling local API: url=%s model=%s", self.settings.local_url, model)

        # Retry logic for JSON parsing failures.
        # Token / elapsed accumulators sum across retries; one terminal
        # record_call is emitted at end of method (success, truncation,
        # error, or exhausted retries).
        max_retries = 3
        last_error: Exception | None = None
        sum_input_tokens = 0
        sum_output_tokens = 0
        any_usage = False
        last_finish_reason: str | None = None
        last_response_model: str | None = None
        attempts_used = 0

        for attempt in range(max_retries):
            attempts_used = attempt + 1
            try:
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
                except asyncio.CancelledError:
                    raise
                except Exception:
                    self._record_call(
                        request_model=model, response_model=None,
                        input_chars=input_chars,
                        elapsed_ms=int((time.perf_counter() - t0) * 1000),
                        outcome="error", prompt_template=prompt_template,
                        input_tokens=sum_input_tokens if any_usage else None,
                        output_tokens=sum_output_tokens if any_usage else None,
                        retry_count=max(attempts_used - 1, 0),
                        usage_source="reported" if any_usage else "missing",
                    )
                    raise

                # Track token usage (Ollama provides this)
                if hasattr(response, "usage") and response.usage:
                    inp = response.usage.prompt_tokens or 0
                    out = response.usage.completion_tokens or 0
                    sum_input_tokens += inp
                    sum_output_tokens += out
                    any_usage = True
                    self.tracker.record(inp, out)
                    logger.info(
                        "LLM call: model=%s input_tokens=%d output_tokens=%d",
                        model, inp, out,
                    )

                last_finish_reason = response.choices[0].finish_reason
                last_response_model = getattr(response, "model", None)

                # Detect truncated response
                if last_finish_reason == "length":
                    self._record_call(
                        request_model=model,
                        response_model=last_response_model,
                        input_chars=input_chars,
                        elapsed_ms=int((time.perf_counter() - t0) * 1000),
                        outcome="truncated", prompt_template=prompt_template,
                        input_tokens=sum_input_tokens if any_usage else None,
                        output_tokens=sum_output_tokens if any_usage else None,
                        finish_reason=last_finish_reason,
                        retry_count=attempts_used - 1,
                        usage_source="reported" if any_usage else "missing",
                    )
                    raise RuntimeError(
                        f"LLM response was truncated (hit max_tokens={max_tokens}). "
                        f"Set BRISTLENOSE_LLM_MAX_TOKENS=65536 in your .env file."
                    )

                content = response.choices[0].message.content
                if content is None:
                    raise RuntimeError("Empty response from local model")

                data = json.loads(content)
                logger.debug(
                    "LLM response fields: %s",
                    {k: type(v).__name__ for k, v in data.items()}
                    if isinstance(data, dict)
                    else type(data).__name__,
                )
                validated = response_model.model_validate(data)
                self._record_call(
                    request_model=model,
                    response_model=last_response_model,
                    input_chars=input_chars,
                    elapsed_ms=int((time.perf_counter() - t0) * 1000),
                    outcome="ok", prompt_template=prompt_template,
                    input_tokens=sum_input_tokens if any_usage else None,
                    output_tokens=sum_output_tokens if any_usage else None,
                    finish_reason=last_finish_reason,
                    retry_count=attempts_used - 1,
                    usage_source="reported" if any_usage else "missing",
                )
                return validated

            except json.JSONDecodeError as e:
                last_error = e
                logger.debug(
                    "JSON parse failed (attempt %d/%d): %s", attempt + 1, max_retries, e
                )
                if attempt < max_retries - 1:
                    await asyncio.sleep(0.5 * (attempt + 1))  # Backoff
            except Exception as e:
                # Catch Pydantic ValidationError and other parsing issues
                if "ValidationError" in type(e).__name__ or "validation" in str(e).lower():
                    last_error = e
                    logger.debug(
                        "Schema validation failed (attempt %d/%d): %s",
                        attempt + 1,
                        max_retries,
                        e,
                    )
                    if attempt < max_retries - 1:
                        await asyncio.sleep(0.5 * (attempt + 1))  # Backoff
                else:
                    raise  # Re-raise non-validation errors

        # All retries exhausted on parse/validation failures.
        self._record_call(
            request_model=model,
            response_model=last_response_model,
            input_chars=input_chars,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            outcome="error", prompt_template=prompt_template,
            input_tokens=sum_input_tokens if any_usage else None,
            output_tokens=sum_output_tokens if any_usage else None,
            finish_reason=last_finish_reason,
            retry_count=max_retries - 1,
            usage_source="reported" if any_usage else "missing",
        )
        raise RuntimeError(
            f"Local model failed to produce valid JSON after {max_retries} attempts. "
            f"Last error: {last_error}. "
            f"Try a larger model (--model llama3.1:8b) or use a cloud API (--llm claude)."
        )
