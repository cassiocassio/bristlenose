/**
 * Put a board file on the clipboard, for the Bristlenose apps in Miro and FigJam to paste.
 *
 * Two flavours, as `figjam-plugin/src/clipboard.ts` reads them: the HTML flavour carries the
 * board JSON, base64 of its UTF-8 bytes, in a `data-bristlenose-board` attribute; the plain
 * flavour carries the board's title, so a ⌘V that lands on the canvas instead of the panel makes
 * a readable line, not raw JSON.
 *
 * Safari: the board is fetched, and a clipboard write after an `await` has lost the click that
 * allowed it. So `clipboard.write()` is called inside the click, with a `ClipboardItem` whose
 * contents are the pending fetch (frontend/gotchas.md § "Clipboard copy after async fetch").
 * Where there is no `ClipboardItem` (old Firefox, jsdom), the bare JSON goes as plain text after
 * the fetch, which both panels also read.
 *
 * @module boardClipboard
 */

/** The board file as the server sends it: only what this reads. */
export interface BoardFile {
  title?: unknown;
  totals: { quotes: number };
}

function base64Utf8(text: string): string {
  const bytes = new TextEncoder().encode(text);
  let binary = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(binary);
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

function titleOf(board: BoardFile): string {
  return typeof board.title === "string" ? board.title : "";
}

/** The HTML flavour: the board in an attribute, its title as the visible text. */
export function boardClipboardHtml(board: BoardFile): string {
  const json = JSON.stringify(board);
  return `<meta charset="utf-8"><div data-bristlenose-board="${base64Utf8(json)}">${escapeHtml(titleOf(board))}</div>`;
}

/**
 * Copy the board `fetchBoard` returns. Call it synchronously in the click handler. Resolves with
 * the board once it is on the clipboard; rejects with the fetch's own error if the board could not
 * be made (so a refusal's `reason` reaches the caller), or with the clipboard's if the copy was
 * refused.
 */
export function copyBoardToClipboard(fetchBoard: () => Promise<BoardFile>): Promise<BoardFile> {
  const board = fetchBoard();
  const clip = typeof navigator !== "undefined" ? navigator.clipboard : undefined;
  if (typeof ClipboardItem !== "undefined" && clip?.write) {
    const item = new ClipboardItem({
      "text/html": board.then((b) => new Blob([boardClipboardHtml(b)], { type: "text/html" })),
      "text/plain": board.then((b) => new Blob([titleOf(b)], { type: "text/plain" })),
    });
    const written = clip.write([item]);
    // A failed fetch rejects both; report the fetch's error, which carries the server's reason.
    // The write's own rejection is then read nowhere, so it is observed here, not left unhandled.
    written.catch(() => undefined);
    return board.then((b) => written.then(() => b));
  }
  return board.then(async (b) => {
    if (!clip?.writeText) throw new Error("no clipboard");
    await clip.writeText(JSON.stringify(b));
    return b;
  });
}
