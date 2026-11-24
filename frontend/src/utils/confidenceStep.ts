/**
 * The AutoCode review's confidence thresholds live on a 0.05 grid. Snap by
 * dividing a whole step count by the number of steps: `n / 20` is the correctly
 * rounded double of the label (0.3), whereas `n * 0.05` drifts (6 * 0.05 is
 * 0.30000000000000004). The server compares what it is sent with `>=` and `<`,
 * so a drifted threshold sent a proposal at exactly 0.30 to Exclude.
 */
export const CONFIDENCE_STEP = 0.05;
const STEPS_PER_UNIT = 20;

export function snapToStep(value: number): number {
  return Math.round(value / CONFIDENCE_STEP) / STEPS_PER_UNIT;
}

const twoPlaces = new Map<string, Intl.NumberFormat>();

/**
 * A confidence as the researcher reads it: two decimals in their language's own mark
 * (0.30, 0,30). Shared by the slider's pointers, the review rows and the histogram's
 * tooltips, so the dialog never shows one number two ways.
 */
export function confidenceText(value: number, locale: string): string {
  let f = twoPlaces.get(locale);
  if (!f) {
    try {
      f = new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    } catch {
      f = new Intl.NumberFormat("en", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }
    twoPlaces.set(locale, f);
  }
  return f.format(value);
}
