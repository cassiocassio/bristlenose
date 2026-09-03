/**
 * What to say when AutoCode refuses to start.
 *
 * The server sends a stable `reason` beside its English `detail`
 * (`bristlenose/server/refusal.py`). This maps each reason to a researcher-
 * facing sentence and one of the five message kinds.
 *
 * Why not just show `detail`: it is written for a log. It quotes internal
 * framework ids, and the ambiguous-provider case tells the reader to run
 * `bristlenose use <provider>` — a shell command, which is wrong in the SPA and
 * absurd in the Mac app. Every sentence here replaces one of those.
 *
 * Kinds follow the one rule in `docs/design-pipeline-diagnostic-popover.md`:
 * WARNING where waiting or a prior step fixes it, ERROR where the researcher
 * must change something, INFO where nothing is wrong at all.
 */

import i18n from "../i18n";
import type { MessageKind } from "./messageKind";

interface Refusal {
  kind: MessageKind;
  /** Locale key under `codebook.autocodeRefusal.*`. */
  key: string;
  /** English fallback — must match the `en` locale value. */
  fallback: string;
}

const REFUSALS: Record<string, Refusal> = {
  no_api_key: {
    kind: "error",
    key: "codebook.autocodeRefusal.noApiKey",
    fallback: "Add an API key in Settings first.",
  },
  provider_local: {
    kind: "error",
    key: "codebook.autocodeRefusal.providerLocal",
    fallback: "This needs a cloud AI provider, not a local model.",
  },
  provider_ambiguous: {
    kind: "error",
    key: "codebook.autocodeRefusal.providerAmbiguous",
    fallback: "Choose an AI provider in Settings.",
  },
  no_quotes: {
    // Not an error: the run order is wrong, not the request.
    kind: "warning",
    key: "codebook.autocodeRefusal.noQuotes",
    fallback: "No quotes yet — analyse your sessions first.",
  },
  already_running: {
    kind: "info",
    key: "codebook.autocodeRefusal.alreadyRunning",
    fallback: "Already tagging with this codebook.",
  },
  already_applied: {
    kind: "info",
    key: "codebook.autocodeRefusal.alreadyApplied",
    fallback: "Already applied.",
  },
  template_missing: {
    kind: "error",
    key: "codebook.autocodeRefusal.templateMissing",
    fallback: "That codebook is no longer available.",
  },
};

/** Resolve a refusal reason to a message and kind, or null if unrecognised. */
export function autocodeRefusal(
  reason: string | undefined,
): { message: string; kind: MessageKind } | null {
  const entry = reason ? REFUSALS[reason] : undefined;
  if (!entry) return null;
  return {
    message: i18n.t(entry.key, { defaultValue: entry.fallback }),
    kind: entry.kind,
  };
}
