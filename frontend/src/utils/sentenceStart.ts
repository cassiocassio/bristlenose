/**
 * Whether a transcript paragraph begins a sentence, so its first letter is
 * drawn as a capital (owner, 6 Oct 2026, option C of
 * docs/mockups/transcript-paragraph-capitalisation.html). Display only: the
 * stored text and the drawn words are never changed.
 *
 * A paragraph begins a sentence when it is the first, when a different speaker
 * spoke the one before, or when the one before ended a sentence. Sentence ends
 * are read from the stored text, which carries punctuation more often than the
 * word timings do; a paragraph that carries on mid-sentence after a split stays
 * as it was transcribed.
 */

/** Ends a sentence: . ? ! … and their CJK, Devanagari and Arabic forms, then any
 *  closing quotes or brackets (German “, French and Russian », with or without a
 *  space), then any bracketed stage directions — "ok. (laughs)". Greek's ; is not
 *  here: it is a semicolon everywhere else. */
const SENTENCE_END =
  /[.?!…。？！।؟](?:["'”’“»›)\]]|\s)*(?:[([][^\])]*[\])]\s*)*$/;

export function startsSentence(
  segments: readonly { speaker_code: string; text: string }[],
  index: number,
): boolean {
  if (index <= 0) return true;
  const before = segments[index - 1];
  const here = segments[index];
  if (!before || !here || before.speaker_code !== here.speaker_code) return true;
  return SENTENCE_END.test(before.text);
}

/** A first word whose lower-case start is its spelling — iPhone, eBay, macOS,
 *  ikea.com — which a drawn capital would misspell. Leading brackets and
 *  quotes are skipped. Not seen at a sentence start in 3,237 real paragraphs
 *  (experiments/paragraph-case); cheap insurance. */
const OWN_SPELLING = /^[^\p{L}\p{N}]*(?:\p{Ll}+\p{Lu}|[\p{Ll}\p{N}-]+\.(?:com|org|net|io|app|co|uk)\b)/u;

/** Whether a paragraph's first letter is drawn as a capital: it begins a
 *  sentence, and its first drawn word is not spelled lower-case on purpose. */
export function drawsCapital(
  segments: readonly { speaker_code: string; text: string }[],
  index: number,
  firstWord: string,
): boolean {
  return startsSentence(segments, index) && !OWN_SPELLING.test(firstWord);
}
