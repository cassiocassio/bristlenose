"""Shared LLM-failure classifier — the single source of "what kind of failure?".

Maps a provider API error (an SDK exception, or its status + code + message)
to a semantic :class:`LLMFailureKind`. One vocabulary, one rule set, used by
every place that has to tell the user *why* an LLM call failed:

- the run-failure cause builder (:mod:`bristlenose.run_lifecycle`),
- the API-key preflight (:mod:`bristlenose.preflight.api_key`),
- the CLI failure banner (:mod:`bristlenose.cli`),
- and — mirrored in Swift — the desktop Settings probe (`LLMValidator`) and
  the failed-run row / out-of-credit pill.

Precedence (research-derived, 2025-2026 provider behaviour):

1. the provider's structured error field — OpenAI ``error.code``, Anthropic
   ``error.type``, Gemini ``error.status`` / ``details[].reason``,
2. then a distinguishing **message substring**,
3. then the HTTP status, as a last resort only.

**Never classify Anthropic or OpenAI billing on the HTTP status alone.**
Anthropic serves out-of-credit as a **400** (``invalid_request_error`` +
"credit balance is too low"), NOT the documented 402; OpenAI shares **429**
between billing exhaustion (``insufficient_quota``) and ordinary rate limiting
(``rate_limit_exceeded``). Status code alone conflates both.

Honesty about coverage: ``OUT_OF_CREDIT`` is only emitted where the wire
actually isolates billing death — **Anthropic and OpenAI**. Azure has no
per-account credit (subscription quota only) and Gemini folds rate-limit,
quota, and free-tier-cap all into one ``RESOURCE_EXHAUSTED`` signal, so their
"you've hit a wall" case classifies as ``RATE_LIMITED`` — we don't fake a
top-up story the provider didn't tell us.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class LLMFailureKind(str, Enum):
    """Semantic classification of an LLM API failure."""

    OUT_OF_CREDIT = "out_of_credit"  # billing exhausted; terminal until top-up
    RATE_LIMITED = "rate_limited"  # transient; back off and retry
    INVALID_KEY = "invalid_key"  # auth failed; fix/replace the key
    SERVER_ERROR = "server_error"  # provider 5xx / overloaded; transient
    BAD_REQUEST = "bad_request"  # malformed / model-not-found; NOT billing
    NETWORK = "network"  # couldn't reach the provider
    UNKNOWN = "unknown"


# Provider slugs as used internally (config values, not display names).
_ANTHROPIC = "anthropic"
_OPENAI = "openai"
_AZURE = "azure"
_GOOGLE = "google"


@dataclass(frozen=True)
class _Rule:
    """One classification rule. All *specified* signals must match; a rule with
    a ``providers`` set applies only to those providers (or when the provider is
    unknown — best-effort for the generic, provider-less path)."""

    kind: LLMFailureKind
    providers: frozenset[str] | None = None
    code: str | None = None  # regex vs the structured code/type/reason field
    message: str | None = None  # regex vs the error message text
    status: int | None = None
    status_range: tuple[int, int] | None = None
    _code_re: re.Pattern[str] | None = field(default=None, init=False, repr=False)
    _msg_re: re.Pattern[str] | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.code is not None:
            object.__setattr__(self, "_code_re", re.compile(self.code, re.IGNORECASE))
        if self.message is not None:
            object.__setattr__(self, "_msg_re", re.compile(self.message, re.IGNORECASE))

    def matches(
        self, provider: str | None, status: int | None, code: str | None, message: str | None
    ) -> bool:
        if self.providers is not None and provider is not None and provider not in self.providers:
            return False
        specified = False
        if self._code_re is not None:
            specified = True
            if code is None or not self._code_re.search(code):
                return False
        if self._msg_re is not None:
            specified = True
            if message is None or not self._msg_re.search(message):
                return False
        if self.status is not None:
            specified = True
            if status != self.status:
                return False
        if self.status_range is not None:
            specified = True
            lo, hi = self.status_range
            if status is None or not (lo <= status <= hi):
                return False
        return specified  # a rule with no signal never matches


# Ordered MOST-SPECIFIC-FIRST — first match wins. Structured-field rules precede
# message rules precede bare-status rules, per the precedence discipline above.
_RULES: tuple[_Rule, ...] = (
    # --- OUT_OF_CREDIT — only Anthropic + OpenAI expose it on the wire. ---
    # Anthropic: the REAL path is a 400 carrying this message (not the 402).
    _Rule(LLMFailureKind.OUT_OF_CREDIT, providers=frozenset({_ANTHROPIC}),
          message=r"credit balance is too low"),
    # Anthropic documented 402 billing_error (rarer than the 400 path).
    _Rule(LLMFailureKind.OUT_OF_CREDIT, providers=frozenset({_ANTHROPIC}),
          code=r"billing_error"),
    # OpenAI: 429 disambiguated by code — insufficient_quota is terminal billing.
    _Rule(LLMFailureKind.OUT_OF_CREDIT, providers=frozenset({_OPENAI}),
          code=r"insufficient_quota"),
    _Rule(LLMFailureKind.OUT_OF_CREDIT, providers=frozenset({_OPENAI}),
          message=r"exceeded your current quota"),

    # --- INVALID_KEY ---
    _Rule(LLMFailureKind.INVALID_KEY, providers=frozenset({_ANTHROPIC}),
          code=r"authentication_error"),
    _Rule(LLMFailureKind.INVALID_KEY, providers=frozenset({_OPENAI}),
          code=r"invalid_api_key"),
    _Rule(LLMFailureKind.INVALID_KEY, providers=frozenset({_OPENAI}),
          message=r"incorrect api key provided"),
    # Gemini: malformed key (400) vs unauthorized/leaked key (403) — both "fix key".
    _Rule(LLMFailureKind.INVALID_KEY, providers=frozenset({_GOOGLE}),
          code=r"API_KEY_INVALID"),
    _Rule(LLMFailureKind.INVALID_KEY, providers=frozenset({_GOOGLE}),
          code=r"PERMISSION_DENIED"),
    _Rule(LLMFailureKind.INVALID_KEY, message=r"api key not valid"),
    _Rule(LLMFailureKind.INVALID_KEY, status=401),
    _Rule(LLMFailureKind.INVALID_KEY, status=403),

    # --- RATE_LIMITED — includes Azure quota + Gemini RESOURCE_EXHAUSTED, which
    #     the wire does not separate from billing; classified honestly as rate. ---
    _Rule(LLMFailureKind.RATE_LIMITED, providers=frozenset({_OPENAI}),
          code=r"rate_limit_exceeded"),
    _Rule(LLMFailureKind.RATE_LIMITED, providers=frozenset({_ANTHROPIC}),
          code=r"rate_limit_error"),
    _Rule(LLMFailureKind.RATE_LIMITED, providers=frozenset({_GOOGLE}),
          code=r"RESOURCE_EXHAUSTED"),
    _Rule(LLMFailureKind.RATE_LIMITED, message=r"rate limit|exceeded token rate limit"),
    _Rule(LLMFailureKind.RATE_LIMITED, status=429),

    # --- SERVER_ERROR — provider-side, transient. ---
    _Rule(LLMFailureKind.SERVER_ERROR, providers=frozenset({_ANTHROPIC}),
          code=r"overloaded_error"),
    _Rule(LLMFailureKind.SERVER_ERROR, status=529),
    _Rule(LLMFailureKind.SERVER_ERROR, status_range=(500, 599)),

    # --- BAD_REQUEST — a real client error (bad model id, malformed body). Last
    #     so a credit-400 / gemini-key-400 is caught above, not swallowed here. ---
    _Rule(LLMFailureKind.BAD_REQUEST, status_range=(400, 499)),
)


def classify_llm_failure(
    provider: str | None = None,
    *,
    status: int | None = None,
    error_code: str | None = None,
    message: str | None = None,
) -> LLMFailureKind:
    """Classify an LLM failure from its structured signals.

    ``provider`` is the internal slug (``anthropic`` / ``openai`` / ``azure`` /
    ``google``); ``None`` runs the rules provider-agnostically (best-effort,
    used by the generic exception path that doesn't know the provider).
    ``error_code`` is the provider's structured discriminator (OpenAI
    ``error.code``, Anthropic ``error.type``, Gemini ``error.status`` or
    ``details[].reason``). Returns :attr:`LLMFailureKind.UNKNOWN` if nothing
    matches.
    """
    for rule in _RULES:
        if rule.matches(provider, status, error_code, message):
            return rule.kind
    return LLMFailureKind.UNKNOWN


def classify_exception(provider: str | None, exc: BaseException) -> LLMFailureKind:
    """Classify from a (possibly SDK) exception by extracting status/code/message.

    Best-effort field extraction across the Anthropic / OpenAI / Google SDK
    exception shapes — they all expose an HTTP status and a structured body,
    just under different attribute names. Falls back to ``str(exc)`` for the
    message so the substring rules still fire on a wrapped/stringified error.
    """
    status = _extract_status(exc)
    code = _extract_code(exc)
    message = str(exc) or exc.__class__.__name__
    return classify_llm_failure(
        provider, status=status, error_code=code, message=message
    )


def _extract_status(exc: BaseException) -> int | None:
    """Pull an HTTP status from common SDK exception attributes."""
    for attr in ("status_code", "code", "http_status"):
        val = getattr(exc, attr, None)
        if isinstance(val, int):
            return val
        if isinstance(val, str) and val.isdigit():
            return int(val)
    resp = getattr(exc, "response", None)
    status = getattr(resp, "status_code", None)
    return status if isinstance(status, int) else None


def _extract_code(exc: BaseException) -> str | None:
    """Pull the provider's structured error code/type/reason from an SDK exc.

    Anthropic exposes ``.body["error"]["type"]``; OpenAI exposes ``.code`` and
    ``.type``; Gemini surfaces ``status`` / ``details[].reason``. We concatenate
    whatever's present so the code-regex rules can match any of them.
    """
    parts: list[str] = []
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        err = body.get("error")
        if isinstance(err, dict):
            for key in ("type", "code", "status", "reason"):
                val = err.get(key)
                if isinstance(val, str):
                    parts.append(val)
            details = err.get("details")
            if isinstance(details, list):
                for d in details:
                    if isinstance(d, dict) and isinstance(d.get("reason"), str):
                        parts.append(d["reason"])
    for attr in ("code", "type"):
        val = getattr(exc, attr, None)
        if isinstance(val, str):
            parts.append(val)
    return " ".join(parts) if parts else None
