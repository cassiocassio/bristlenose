/**
 * searchKeys — what the search field's keys do to the suggestions list and the
 * tokens (docs/design-search.md §6). Pure, and the same decisions the Mac
 * field makes (`SearchFieldKeys` in SearchFieldViews.swift), so both surfaces
 * behave alike and each is tested without driving key events.
 */

import { foldKey } from "./searchMatch";
import type { SearchToken } from "./searchTokens";

/** ↓ / ↑ move the highlight by row id and wrap; no highlight means the first
 *  row, so ↓ from there goes to the second and ↑ to the last. */
export function moveHighlight(highlight: string | null, step: number, rows: string[]): string | null {
  if (rows.length === 0) return null;
  const at = highlight !== null && rows.includes(highlight) ? rows.indexOf(highlight) : 0;
  return rows[(((at + step) % rows.length) + rows.length) % rows.length];
}

/** The highlighted row: this id if it is still offered, else the first (the
 *  free text, which ↩ takes by default). */
export function highlightedRow(id: string | null, rows: string[]): string | null {
  if (id !== null && rows.includes(id)) return id;
  return rows[0] ?? null;
}

/** A token's identity: its person or its tag, never its position. */
export function tokenKey(token: SearchToken): string {
  return token.kind === "person" ? `person:${token.code}` : `tag:${foldKey(token.name)}`;
}

export type BackspaceAction =
  | { kind: "select"; key: string }
  | { kind: "remove"; token: SearchToken }
  | { kind: "passThrough" };

/** ⌫ in an empty field selects the last token; a second press removes it, so
 *  one slip can't delete a token (§6). */
export function backspaceAction(
  text: string,
  tokens: SearchToken[],
  selected: string | null,
): BackspaceAction {
  const last = tokens[tokens.length - 1];
  if (text !== "" || !last) return { kind: "passThrough" };
  return selected === tokenKey(last) ? { kind: "remove", token: last } : { kind: "select", key: tokenKey(last) };
}
