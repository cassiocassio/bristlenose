/**
 * The words a signal's chip says, resolved once for the card and for the navigation.
 *
 * The server resolves them (`sentiment_label.py`): one of the seven feelings ("Frustration"), a
 * direction ("Positive", "Negative") when no single feeling is the honest name, or "Mixed
 * sentiments". A codebook card says its group's name. The navigation uses the same words, with
 * "Mixed" for the long "Mixed sentiments", so the row and the card never name one signal two
 * ways (owner, 30 Oct 2026).
 */
import type { TFunction } from "i18next";
import { getBarColour } from "./colours";
import type { UnifiedSignal } from "./types";

const SUMMARY_KEYS: Record<string, { long: string; short?: string }> = {
  Positive: { long: "signals.labelPositive" },
  Negative: { long: "signals.labelNegative" },
  "Mixed sentiments": { long: "signals.labelMixed", short: "signals.labelMixedShort" },
};

export interface ChipWords {
  /** The value the server sent, or the column label on a response that predates it. */
  raw: string;
  /** What to print. */
  label: string;
  /** A named feeling, translated by the `enums` namespace. */
  isValue: boolean;
}

/**
 * @param te the `enums` namespace translator (sentiment values)
 * @param tc the `common` namespace translator (the summary labels)
 * @param short the navigation's form: "Mixed" for "Mixed sentiments"
 */
export function chipWords(
  signal: UnifiedSignal,
  isSentiment: boolean,
  te: TFunction,
  tc: TFunction,
  short = false,
): ChipWords {
  const raw = signal.label || signal.columnLabel;
  const isValue = signal.labelKind === "value" || isSentiment;
  const summary = SUMMARY_KEYS[raw];
  const label = isValue
    ? te(`sentiment.${raw}`, { defaultValue: raw })
    : summary
      ? tc(short && summary.short ? summary.short : summary.long, { defaultValue: raw })
      : raw;
  return { raw, label, isValue };
}

/**
 * The hue a signal carries: the colour the card's keyline, hover tint and ink are all derived
 * from (`signals.css`), and the one the navigation's mini tag takes so the two match.
 */
export function signalAccent(signal: UnifiedSignal, isSentiment: boolean): string {
  if (isSentiment) return `var(--bn-sentiment-${signal.columnLabel})`;
  return signal.colourSet ? getBarColour(signal.colourSet) : "var(--bn-colour-accent)";
}
