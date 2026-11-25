/**
 * Fixture data for the session timeline stories: one 45-minute interview in the shape
 * GET /api/projects/{id}/tapestry returns (utils/types.ts `TapestrySession`), and transcription
 * quality records in the shape `bristlenose/transcription_quality.py` writes (version 1).
 *
 * Generated from a fixed seed so every render is the same session: turns alternate moderator and
 * participant, every turn carries its section's scene colour (what was on screen, whoever spoke),
 * and the quotes sit inside the participant's turns. No video, so no scene strip and no hover
 * thumbnail (`strip` and `frames_key` are null).
 */

import type { TranscriptionQuality } from "../../../components/TranscriptionDiagnostics";
import type { TapestryQuote, TapestrySession, TapestryTurn } from "../../../utils/types";

const DURATION = 45 * 60;

/** Small deterministic PRNG (mulberry32), so the fixture never changes between renders. */
function seeded(seed: number): () => number {
  let a = seed;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const SECTIONS = [
  { t0: 0, label: "Introductions", colour: "#e6e3dc" },
  { t0: 150, label: "Browsing the homepage", colour: "#d8e7f5" },
  { t0: 600, label: "Searching for a product", colour: "#f2e2c4" },
  { t0: 1140, label: "Product page", colour: "#e4efd9" },
  { t0: 1620, label: "Basket and delivery", colour: "#f4d6d2" },
  { t0: 2160, label: "Checkout and payment", colour: "#e2dcf1" },
  { t0: 2520, label: "Wrap-up", colour: "#e6e3dc" },
] as const;

const sectionAt = (t: number) => [...SECTIONS].reverse().find((s) => s.t0 <= t) ?? SECTIONS[0];

function makeTurns(): TapestryTurn[] {
  const rnd = seeded(7);
  const turns: TapestryTurn[] = [];
  let t = 0;
  let moderator = true;
  while (t < DURATION) {
    const len = moderator ? 6 + rnd() * 22 : 20 + rnd() * 75;
    const t1 = Math.min(DURATION, t + len);
    const section = sectionAt(t);
    turns.push({
      t0: Math.round(t),
      t1: Math.round(t1),
      speaker: moderator ? "m1" : "p1",
      team: moderator,
      colour: section.colour,
    });
    t = t1;
    moderator = !moderator;
  }
  return turns;
}

const QUOTES: { at: number; text: string; sentiment: string | null; intensity: number; theme: string | null }[] = [
  { at: 210, text: "I'd normally go straight to the search bar.", sentiment: "confidence", intensity: 1, theme: null },
  { at: 380, text: "There's a lot going on here, I don't know where to look.", sentiment: "confusion", intensity: 2, theme: "Too much on the homepage" },
  { at: 520, text: "Oh, that's nice, the sale banner.", sentiment: "delight", intensity: 1, theme: null },
  { at: 700, text: "It came up with jars straight away.", sentiment: "satisfaction", intensity: 2, theme: null },
  { at: 860, text: "Why is it showing me cushions?", sentiment: "frustration", intensity: 2, theme: "Search misses what I typed" },
  { at: 1010, text: "I didn't expect it to have that many sizes.", sentiment: "surprise", intensity: 1, theme: null },
  { at: 1240, text: "The photos are good, I can see the lid.", sentiment: "satisfaction", intensity: 1, theme: null },
  { at: 1400, text: "I'm not sure if that's per jar or for the set.", sentiment: "doubt", intensity: 2, theme: "Price per what?" },
  { at: 1700, text: "Twelve pounds for delivery? No.", sentiment: "frustration", intensity: 3, theme: "Delivery cost arrives too late" },
  { at: 1900, text: "I'd want to know that before I'd put anything in.", sentiment: "frustration", intensity: 2, theme: "Delivery cost arrives too late" },
  { at: 2050, text: "Click and collect, fine, that works for me.", sentiment: "confidence", intensity: 1, theme: null },
  { at: 2240, text: "Why does it want my phone number?", sentiment: "doubt", intensity: 2, theme: null },
  { at: 2400, text: "That was quicker than I thought.", sentiment: "delight", intensity: 2, theme: null },
  { at: 2600, text: "We usually do this on a Sunday, the two of us.", sentiment: null, intensity: 1, theme: "Shopping as a household chore" },
];

function makeQuotes(turns: TapestryTurn[]): TapestryQuote[] {
  return QUOTES.map((q) => {
    // Inside the participant turn nearest the moment, so a quote is always something they said.
    const turn = turns
      .filter((tn) => tn.speaker === "p1")
      .reduce((best, tn) => (Math.abs(tn.t0 - q.at) < Math.abs(best.t0 - q.at) ? tn : best));
    const t0 = turn.t0 + 2;
    return {
      t0,
      t1: Math.min(turn.t1, t0 + 12),
      text: q.text,
      sentiment: q.sentiment,
      intensity: q.intensity,
      section: sectionAt(t0).label,
      theme: q.theme,
    };
  });
}

const TURNS = makeTurns();

export const TAPESTRY_SESSION: TapestrySession = {
  session_id: "s-sg-1",
  duration_seconds: DURATION,
  turns: TURNS,
  sections: SECTIONS.map(({ t0, label }) => ({ t0, label })),
  quotes: makeQuotes(TURNS),
  strip: null,
  frames_key: null,
  strip_state: null,
};

export const NAMES: Record<string, string> = { m1: "Rachel", p1: "Alex" };

const BIN = 30;
const BINS = Math.ceil(DURATION / BIN);

function series(): TranscriptionQuality["series"] {
  const rnd = seeded(11);
  return {
    bin_s: BIN,
    level_p90: Array.from({ length: BINS }, (_, i) => (i >= 40 && i < 43 ? null : -24 + rnd() * 10)),
    wpm: Array.from({ length: BINS }, () => Math.round(110 + rnd() * 70)),
    low_conf: Array.from({ length: BINS }, (_, i) => (i >= 40 && i < 43 ? null : 0.03 + rnd() * (i > 55 && i < 62 ? 0.4 : 0.1))),
  };
}

/** Whisper (mlx) with its repair net: retried windows, stretches found and one still empty. */
export const QUALITY_WHISPER: TranscriptionQuality = {
  version: 1,
  session_id: "s-sg-1",
  duration_s: DURATION,
  audio: { floor_dbfs: -52, peak_dbfs: -6, active_share: 0.78, clipped_share: 0 },
  recognition: {
    backend: "mlx", model: "large-v3-turbo", transcribed: true, language: "en",
    language_set: false, prompt: true, decode_windows: 90, fallback_windows: 7,
    mean_confidence: 0.88, low_confidence_share: 0.09,
  },
  repair: {
    silent_dropped: 0, echoes_dropped: 2, loop_segments_removed: 0,
    skipped_found: 3, skipped_seconds: 64, skipped_recovered: 2, recovered_words: 140,
    found: [[1200, 1230], [1660, 1684], [1760, 1770]], still_empty: [[1760, 1770]],
    inaudible_gaps: 2, inaudible_seconds: 5,
  },
  text: { words: 5600, wpm: 141, sentence_ends_per_100: 8.7, longest_unpunctuated: 31 },
  series: series(),
};

/** Apple's speech model, whose guessed locale did not hold: the session was left for Whisper. */
export const QUALITY_GATE_FAILED: TranscriptionQuality = {
  ...QUALITY_WHISPER,
  recognition: {
    backend: "apple-speech", transcribed: true, locale: "en-GB", locale_source: "assumed",
    mean_confidence: 0.41, low_confidence_share: 0.48,
    gate: { passed: false, reason: "low confidence", mean_confidence: 0.41, words_per_signal_minute: 38, signal_minutes: 35 },
  },
  repair: { inaudible_gaps: 0, inaudible_seconds: 0 },
};

/** faster-whisper: no decode windows, no repair net, no audio levels; the lanes it lacks are left out. */
export const QUALITY_SPARSE: TranscriptionQuality = {
  ...QUALITY_WHISPER,
  audio: null,
  recognition: { backend: "faster-whisper", mean_confidence: 0.9, low_confidence_share: 0.05 },
  repair: { inaudible_gaps: 0, inaudible_seconds: 0 },
  series: { ...QUALITY_WHISPER.series, level_p90: QUALITY_WHISPER.series.level_p90.map(() => null) },
};
