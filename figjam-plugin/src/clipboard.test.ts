import { describe, expect, it } from "vitest";
import { boardTextFromClipboard } from "./clipboard";

// The board travels as base64 of its UTF-8 bytes, so text in any script survives.
const board = '{"title":"Café — 読書","quotes":["“It said available.”"]}';
const base64 = btoa(String.fromCharCode(...new TextEncoder().encode(board)));

describe("boardTextFromClipboard", () => {
  it("reads the board from the HTML flavour, not the readable plain text beside it", () => {
    const html = `<meta charset="utf-8"><div data-bristlenose-board="${base64}">Café — 3 quotes</div>`;
    expect(boardTextFromClipboard(html, "Café — 3 quotes")).toBe(board);
  });

  it("accepts the attribute in single quotes", () => {
    expect(boardTextFromClipboard(`<div data-bristlenose-board='${base64}'></div>`, "")).toBe(board);
  });

  it("falls back to plain text when the HTML carries no board", () => {
    expect(boardTextFromClipboard("<p>some other copy</p>", board)).toBe(board);
    expect(boardTextFromClipboard("", board)).toBe(board);
  });

  it("falls back to plain text when the board attribute is not valid UTF-8", () => {
    const broken = btoa("\xff\xfe\xfd");
    expect(boardTextFromClipboard(`<div data-bristlenose-board="${broken}"></div>`, "plain")).toBe("plain");
  });
});
