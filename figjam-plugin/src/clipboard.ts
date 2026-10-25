// A board pasted into the panel. Bristlenose can put the board on the clipboard
// as two flavours: the board JSON, base64 of its UTF-8 bytes, in a
// data-bristlenose-board attribute of the HTML flavour, and readable text as the
// plain flavour, so a ⌘V on the canvas makes readable text, not raw JSON
// (measured 19 Oct 2026). Bare board JSON as plain text works too.
//
// The attribute is found by a pattern, not parsed as a page: base64 has no
// quotes or angle brackets, and nothing from the clipboard is put into the panel.

const BOARD_ATTRIBUTE = /data-bristlenose-board\s*=\s*["']([A-Za-z0-9+/=\s]+)["']/;

export function boardTextFromClipboard(html: string, plain: string): string {
  const match = BOARD_ATTRIBUTE.exec(html);
  if (!match) return plain;
  try {
    const binary = atob(match[1].replace(/\s+/g, ""));
    const bytes = Uint8Array.from(binary, (c) => c.charCodeAt(0));
    return new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return plain;
  }
}
