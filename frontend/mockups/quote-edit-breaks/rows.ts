/**
 * Every key and gesture on a quote card, shipped and proposed.
 *
 * `shipped` is what islands/QuoteCard.tsx + hooks/useCropEdit.ts do, read from
 * the code. Click, Shift-Return, Option-Return, Tab in both modes and the trim
 * drag were checked on the live card in Chromium on 21 Nov 2026; paste was not.
 * `proposed: "same"` means the proposal does not change it.
 */

export interface Row {
  group: string;
  key: string;
  shipped: string;
  proposed: string;
  /** The proposal leaves this to the owner (a toggle in the bar). */
  open?: boolean;
}

export const ROWS: Row[] = [
  // ── At rest ────────────────────────────────────────────────────────────
  {
    group: "At rest",
    key: "Click the text",
    shipped:
      "Starts editing. The paragraphs fold into one, the quote marks go and the brackets fade in, so the whole card moves. The caret goes to the start.",
    proposed:
      "Starts editing in place: paragraphs, quote marks and … stay where they were, and the brackets fade in over the quote marks. The caret goes where you clicked.",
  },
  {
    group: "At rest",
    key: "⌘-click, Shift-click",
    shipped: "Selects the quote instead of editing it (not wired up on this page).",
    proposed: "same",
  },

  // ── Editing the words ─────────────────────────────────────────────────
  { group: "Editing the words", key: "Typing", shipped: "Edits the words.", proposed: "same" },
  { group: "Editing the words", key: "Return", shipped: "Commits.", proposed: "same" },
  {
    group: "Editing the words",
    key: "Shift-Return",
    shipped:
      "The browser draws a line break. It is thrown away on commit; with no space beside it, the two words it separated are saved run together.",
    proposed:
      "Starts a new paragraph at the caret. Inside a word, the break goes before the word (the transcript's rule for Return). At a paragraph's edge, nothing.",
  },
  {
    group: "Editing the words",
    key: "Option-Return",
    shipped: "Commits, the same as Return: the handler checks only for Shift.",
    proposed: "The same as Shift-Return: the Mac's key for a new line in a one-line field.",
  },
  {
    group: "Editing the words",
    key: "Backspace at a paragraph's start",
    shipped: "There are no paragraphs while editing: it deletes the character before, usually the space, joining two words.",
    proposed: "Joins the paragraph to the one above, as Backspace does in the transcript.",
  },
  {
    group: "Editing the words",
    key: "Delete at a paragraph's end",
    shipped: "Deletes the character after, usually the space, joining two words.",
    proposed: "Joins the paragraph below to this one.",
  },
  {
    group: "Editing the words",
    key: "Backspace at the very start",
    shipped: "Nothing.",
    proposed: "same",
  },
  {
    group: "Editing the words",
    key: "Escape",
    shipped: "Cancels: the quote goes back to how it was.",
    proposed: "Cancels: the words and the paragraphs go back to how they were.",
  },
  {
    group: "Editing the words",
    key: "Tab, Shift-Tab",
    shipped: "Focus moves to the next control (the speaker's name); the edit commits 150 ms later, when the text loses focus.",
    proposed: "Commits at once, then focus moves to the next control. Or, with the toggle, stays on the card.",
    open: true,
  },
  {
    group: "Editing the words",
    key: "Click outside the card",
    shipped: "Commits.",
    proposed: "same",
  },
  {
    group: "Editing the words",
    key: "Paste",
    shipped: "Pastes whatever the clipboard holds, formatting included; only its text is kept on commit.",
    proposed: "Pastes as plain text, on one line, so a pasted paragraph cannot bring its own layout in.",
  },
  {
    group: "Editing the words",
    key: "Drag a bracket",
    shipped: "Switches to trimming.",
    proposed: "same",
  },

  // ── Trimming ──────────────────────────────────────────────────────────
  {
    group: "Trimming",
    key: "Dragging",
    shipped: "The bracket moves through the words and takes room in the line, so the words after it shift as it goes.",
    proposed: "The bracket sits in the gap between two words and takes no room: only the colour changes. The paragraphs stay.",
  },
  { group: "Trimming", key: "Return", shipped: "Commits the trim.", proposed: "same" },
  { group: "Trimming", key: "Escape", shipped: "Cancels.", proposed: "same" },
  {
    group: "Trimming",
    key: "Tab",
    shipped: "Focus leaves, but the card stays in trimming with its brackets showing, until you click outside it.",
    proposed: "Commits, as in editing the words.",
  },
  {
    group: "Trimming",
    key: "Click a kept word",
    shipped: "Back to editing the words, as one paragraph.",
    proposed: "Back to editing the words, paragraphs kept, caret where you clicked.",
  },
  { group: "Trimming", key: "Click outside the card", shipped: "Commits.", proposed: "same" },

  // ── After commit ──────────────────────────────────────────────────────
  {
    group: "After commit",
    key: "Words changed",
    shipped: "Saved as the quote's edit (QuoteEdit).",
    proposed: "same",
  },
  {
    group: "After commit",
    key: "Only paragraphs changed",
    shipped: "Nothing is saved: a change only in spacing is not an edit (decision #30).",
    proposed:
      "Saved as the quote's own paragraphs (quote_breaks, source: researcher), the words untouched. Nothing goes to the transcript.",
  },
  {
    group: "After commit",
    key: "Paragraphs shown",
    shipped: "Placed again automatically from the new words.",
    proposed: "Yours, if you placed or removed any. Otherwise placed again automatically from the new words.",
  },
  {
    group: "After commit",
    key: "Revert (the arrow)",
    shipped:
      "Back to the original words. A trimmed quote keeps its \u2026 in front of them until a reload: a separate bug, seen on this page.",
    proposed: "Back to the original words and the automatic paragraphs. The \u2026 bug is left as it is.",
  },
  {
    group: "After commit",
    key: "Break long paragraphs off",
    shipped: "One paragraph.",
    proposed: "Your own paragraphs still show; automatic ones don't (owner, 21 Nov 2026).",
  },
];
