/**
 * searchSynthetic — a made-up project for testing search. TEST-ONLY: nothing
 * in the app imports this.
 *
 * Deterministic for a given seed, so a failing case reproduces. The people,
 * quotes and tags are shaped to exercise the matching rules: names with
 * accents and in Cyrillic, Chinese, Japanese and Korean script; quotes in those
 * languages; a moderator; tags whose names share prefixes; and a scale knob.
 * No real interview content, no participant data.
 */

import type { SearchPerson } from "./searchSuggest";
import type { QuoteResponse, TagResponse } from "./types";

export interface SyntheticProject {
  quotes: QuoteResponse[];
  people: Record<string, SearchPerson>;
  tags: TagResponse[];
}

export interface SyntheticOptions {
  seed?: number;
  /** One participant per session; participants repeat once the cast runs out. */
  sessions?: number;
  quotesPerSession?: number;
  /** Extra generated tags on top of the named ones (for scale). */
  extraTags?: number;
}

/** mulberry32: a small, well-mixed 32-bit PRNG. */
function prng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** The cast. Codes are slots (p1…), names a layer above, as in the product. */
export const CAST: { full: string; short: string; lang: "en" | "es" | "ru" | "ja" | "ko" | "zh" }[] = [
  { full: "Amira Haddad", short: "Amira", lang: "en" },
  { full: "Tom Fletcher", short: "Tom", lang: "en" },
  { full: "Priya Shah", short: "Priya", lang: "en" },
  { full: "José Núñez", short: "José", lang: "es" },
  { full: "Jo Kim", short: "Jo", lang: "en" },
  { full: "Алёна Смирнова", short: "Алёна", lang: "ru" },
  { full: "山田 花子", short: "花子", lang: "ja" },
  { full: "김민지", short: "", lang: "ko" },
  { full: "陳 美玲", short: "美玲", lang: "zh" },
  { full: "Priyanka Rao", short: "Priyanka", lang: "en" },
];
export const MODERATOR = { code: "m1", full: "Sam Ortiz", short: "Sam" };

const TOPICS = ["delivery", "assembly", "price", "checkout", "measurement", "bookcase", "stock", "returns"];

const EN = [
  "I got all the way to the end and then the {t} was more than the shelf.",
  "Honestly the {t} bit was where I nearly gave up.",
  "I didn’t know whether {t} was included or extra.",
  "The {t} page kept losing what I’d entered.",
  "If they’d said up front about {t} I’d have been fine.",
  "I liked that the {t} information was right there.",
  "I agree with {who} about the {t}, it was confusing.",
];
const BY_LANG: Record<string, string[]> = {
  es: ["No sabía si la entrega costaba más.", "El montaje fue más difícil de lo que pensé."],
  ru: ["Ещё раз проверила доставку, и цена опять выросла.", "Сборка заняла больше времени, чем я думала."],
  ja: ["配送料が最後に分かって驚きました。", "組み立ては思ったより大変でした。"],
  ko: ["배송비가 마지막에 나와서 놀랐어요.", "조립이 생각보다 어려웠어요."],
  zh: ["運費到最後才看到，我很驚訝。", "組裝比我想像的難。"],
};

const NAMED_TAGS = [
  "hidden costs",
  "delivery time",
  "delivery cost",
  "price surprise",
  "assembly",
  "trust",
  "store stock",
  "measurement",
  "returns",
  "checkout friction",
];
const SENTIMENTS = ["frustration", "confusion", "doubt", "surprise", "satisfaction", "delight", "confidence"];

function tag(name: string, i: number): TagResponse {
  const sets = ["ux", "emo", "task", "trust", "opp"];
  return { name, codebook_group: "Synthetic", colour_set: sets[i % sets.length], colour_index: i % 5, source: "human" };
}

export function syntheticProject(options: SyntheticOptions = {}): SyntheticProject {
  const rand = prng(options.seed ?? 42);
  const pick = <T>(xs: readonly T[]): T => xs[Math.floor(rand() * xs.length)];
  const sessions = options.sessions ?? 10;
  const perSession = options.quotesPerSession ?? 6;

  const tags = [
    ...NAMED_TAGS.map(tag),
    ...Array.from({ length: options.extraTags ?? 0 }, (_, i) => tag(`theme ${i + 1}`, i)),
  ];

  const people: Record<string, SearchPerson> = {
    [MODERATOR.code]: { full_name: MODERATOR.full, short_name: MODERATOR.short },
  };
  CAST.forEach((p, i) => {
    people[`p${i + 1}`] = { full_name: p.full, short_name: p.short };
  });

  const quotes: QuoteResponse[] = [];
  for (let s = 0; s < sessions; s++) {
    const castIndex = s % CAST.length;
    const code = `p${castIndex + 1}`;
    const who = CAST[castIndex];
    for (let k = 0; k < perSession; k++) {
      const topic = pick(TOPICS);
      // "{who}" names another English-speaking cast member, so a "mentions"
      // token has something real to find.
      const other = pick(CAST.filter((c, i) => c.lang === "en" && i !== castIndex));
      const text =
        who.lang === "en" || rand() < 0.3
          ? pick(EN).replace("{t}", topic).replace("{who}", other.short)
          : pick(BY_LANG[who.lang]);
      const quoteTags: TagResponse[] = [];
      const n = Math.floor(rand() * 3); // 0–2 tags
      for (let j = 0; j < n; j++) {
        const t = pick(tags);
        if (!quoteTags.some((x) => x.name === t.name)) quoteTags.push(t);
      }
      const start = 30 + k * 95;
      quotes.push({
        dom_id: `q-s${s + 1}-${k}`,
        text,
        verbatim_excerpt: text,
        participant_id: code,
        session_id: `s${s + 1}`,
        speaker_name: who.short || who.full,
        start_timecode: start,
        end_timecode: start + 12,
        sentiment: rand() < 0.8 ? pick(SENTIMENTS) : null,
        intensity: 1 + Math.floor(rand() * 3),
        researcher_context: null,
        quote_type: "screen_specific",
        topic_label: topic,
        is_starred: false,
        is_hidden: false,
        edited_text: null,
        tags: quoteTags,
        deleted_badges: [],
        proposed_tags: [],
        segment_index: k,
      });
    }
  }
  return { quotes, people, tags };
}
