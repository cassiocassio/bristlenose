/**
 * toast() — imperative toast function callable from anywhere.
 *
 * Manages a detached React root on a persistent container div.
 * One toast at a time — a new call replaces the current one, except that a
 * failure holds its window against a lower kind (see `toast`).
 * Drop-in replacement for the vanilla showToast().
 */

import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { createElement } from "react";
import { Toast } from "../components/Toast";
import { announce } from "./announce";
import type { MessageKind } from "./messageKind";

let root: Root | null = null;
let container: HTMLDivElement | null = null;

/** Mounts a fresh `<Toast>` for every call: a replaced toast starts its own timer. */
let seq = 0;
/** The visible toast's rank, or null when none is up. Cleared when that toast is dismissed
 *  (not by a clock: a throttled tab stalls the dismiss timer while the wall clock runs on). */
let held: { rank: number } | null = null;
/** What the visible toast says, so an identical repeat (an outage burst of failed saves)
 *  restarts its timer without replaying the fade-in. */
let current: { message: string; title: string | undefined; kind: MessageKind | undefined } | null = null;

function getContainer(): HTMLDivElement {
  if (!container) {
    container = document.createElement("div");
    container.setAttribute("data-testid", "bn-toast-container");
    document.body.appendChild(container);
  }
  return container;
}

function getRoot(): Root {
  if (!root) {
    root = createRoot(getContainer());
  }
  return root;
}

/** Only the toast that is still up may take itself down: a stale timer from a toast that
 *  has since been replaced must not erase its successor. */
function dismiss(mySeq: number): void {
  if (mySeq !== seq) return;
  held = null;
  current = null;
  getRoot().render(null);
}

/**
 * Unmount the toast root and drop its container (tests). The root is Bristlenose's
 * own, so testing-library's cleanup never sees it: a toast left mounted at the end
 * of a file keeps committing (its fade-in frame, its dismiss timer) after the last
 * test, and a commit the scheduler yields on reads `window` after vitest has torn
 * the environment down. Call inside `act()`.
 */
export function _resetToast(): void {
  root?.unmount();
  root = null;
  container?.remove();
  container = null;
  held = null;
  current = null;
  seq = 0;
}

/**
 * How long a toast stays when its caller names no duration. A failure is held
 * longer than a confirmation: a lost edit that the researcher did not see is not
 * a fact worth 2 s. No kind is a bare confirmation ("Copied").
 */
const DEFAULT_DURATION: Record<MessageKind | "plain", number> = {
  plain: 2000,
  success: 2000,
  skipped: 4000,
  info: 4000,
  warning: 5000,
  error: 6000,
};

/** How a toast ranks. A confirmation (plain or success) is not drawn over a visible warning or
 *  error: it would erase a failure the researcher may not have read. Anything else replaces
 *  what is up, since it answers a newer gesture. */
const RANK: Record<MessageKind | "plain", number> = {
  plain: 0,
  success: 1,
  skipped: 2,
  info: 2,
  warning: 3,
  error: 4,
};

export interface ToastOptions {
  /** A short heading for a message that is already two sentences: what is the case.
   *  `message` is then the body: what to do, or why. No full stop on a title. */
  title?: string;
}

/** Joins a title to its body for the screen reader, in the title's own punctuation. */
function spoken(title: string, body: string): string {
  if (/[.!?。！？]$/.test(title)) return `${title} ${body}`;
  return /[\u3040-\u30ff\u4e00-\u9fff]$/.test(title) ? `${title}。${body}` : `${title}. ${body}`;
}

/**
 * Show a toast notification. One at a time; a failure is not erased by a confirmation.
 *
 * @param message  Text to display (the body, when `options.title` is given)
 * @param duration Auto-dismiss delay in ms. Omit for the default of its kind
 *                 (2 s plain or success, 4 s info, 5 s warning, 6 s error).
 * @param kind     One of the five in `messageKind.ts`. Renders the matching icon.
 *                 Omit for a plain toast — a bare confirmation ("Copied") does
 *                 not need a tick, and adding one to every toast would spend the
 *                 vocabulary on messages that carry no state. A toast draws four
 *                 of the five: `skipped` is drawn as `info`.
 * @param options  `title`, for a message that splits into a heading and a body.
 */
export function toast(
  message: string,
  duration?: number,
  kind?: MessageKind,
  options?: ToastOptions,
): void {
  const title = options?.title;
  // A toast is often the only sign an action happened, so it is spoken too. The
  // shared live region already exists when the toast appears; one born with its
  // text, as this container is on first use, can go unannounced. It is spoken
  // even when a failure keeps the screen: the words are not lost, only not drawn.
  const bare = message.replace(/\s*\n\s*/g, " ");
  announce(title ? spoken(title, bare) : bare);

  const rank = RANK[kind ?? "plain"];
  const ms = duration ?? DEFAULT_DURATION[kind ?? "plain"];
  if (held && rank <= RANK.success && held.rank >= RANK.warning) return;
  const repeat =
    current !== null && current.message === message && current.title === title && current.kind === kind;
  held = { rank };
  current = { message, title, kind };
  seq += 1;
  const mine = seq;
  getRoot().render(
    createElement(Toast, {
      key: mine,
      message,
      title,
      duration: ms,
      kind,
      instant: repeat,
      onDismiss: () => dismiss(mine),
    }),
  );
}
