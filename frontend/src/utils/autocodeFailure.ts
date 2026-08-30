/**
 * What to say when an AutoCode job dies.
 *
 * The server classifies the exception into an `LLMFailureKind`
 * (`bristlenose/llm/failure_classifier.py`) and sends it as `failure_kind`.
 * This maps that to a researcher-facing sentence and one of the five message
 * kinds.
 *
 * Why not show `error_message`: it is `str(exc)` from a bare `except` — raw SDK
 * text, often a stringified JSON body. Both the activity chip and the AutoCode
 * toast interpolated it straight into a sentence, so a rate limit read as
 * `Tagging failed: Error code: 429 - {'type': 'error', ...}`.
 *
 * Kinds follow the rule in `docs/design-pipeline-diagnostic-popover.md`:
 * WARNING where waiting fixes it, ERROR where the researcher must change
 * something. Rate limiting is therefore a warning despite stopping the run —
 * and out-of-credit is emphatically *not* one. Anthropic returns 400 for an
 * exhausted account, so the two are indistinguishable without the classifier,
 * and telling a bankrupt account to "try again shortly" is the specific
 * failure that doc records.
 */

import i18n from "../i18n";
import type { MessageKind } from "./messageKind";

interface Failure {
  kind: MessageKind;
  key: string;
  fallback: string;
}

const FAILURES: Record<string, Failure> = {
  out_of_credit: {
    kind: "error",
    key: "codebook.autocodeFailure.outOfCredit",
    fallback: "Your AI provider account is out of credit.",
  },
  rate_limited: {
    kind: "warning",
    key: "codebook.autocodeFailure.rateLimited",
    fallback: "Rate limited — tagging stopped. Try again soon.",
  },
  invalid_key: {
    kind: "error",
    key: "codebook.autocodeFailure.invalidKey",
    fallback: "Your API key was rejected.",
  },
  server_error: {
    kind: "warning",
    key: "codebook.autocodeFailure.serverError",
    fallback: "The AI provider is unavailable. Try again shortly.",
  },
  bad_request: {
    kind: "error",
    key: "codebook.autocodeFailure.badRequest",
    fallback: "The AI provider rejected the request.",
  },
  network: {
    kind: "warning",
    key: "codebook.autocodeFailure.network",
    fallback: "Couldn't reach the AI provider. Check your connection.",
  },
  unknown: {
    kind: "error",
    key: "codebook.autocodeFailure.unknown",
    fallback: "Tagging failed.",
  },
};

/**
 * Resolve a `failure_kind` to a sentence and kind.
 *
 * Falls back to the generic "Tagging failed." for an unclassified job — every
 * job that failed before `failure_kind` existed, and any the classifier
 * declined to name. Never returns the raw exception text.
 */
export function autocodeFailure(failureKind: string | undefined): {
  message: string;
  kind: MessageKind;
} {
  const entry = (failureKind && FAILURES[failureKind]) || FAILURES.unknown;
  return {
    message: i18n.t(entry.key, { defaultValue: entry.fallback }),
    kind: entry.kind,
  };
}
