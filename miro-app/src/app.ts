// The panel Miro opens from the toolbar: choose, drop or paste a Bristlenose board file, then
// watch it build into the open board. The panel calls Miro's SDK itself; there is no other code
// and nothing is sent anywhere but Miro. Text from the file is never put into this page: status
// lines are set with textContent only, and the stickies' HTML is built and escaped in layout.ts.

import { MAX_FILE_BYTES, REFUSAL_TEXT, Refusal, type RefusalKind, parseBoard } from "../../figjam-plugin/src/board";
import { boardTextFromClipboard } from "../../figjam-plugin/src/clipboard";
import { type BoardApi, NOT_CONNECTED, Stopped, draw } from "./draw";
import { type BoardPlan, planBoard } from "./layout";
import { failure, summary } from "./summary";

declare const miro: { board: BoardApi };

// FigJam's refusals say "update the plugin"; this app updates itself when the board reloads.
const REFUSALS: Record<RefusalKind, string> = {
  ...REFUSAL_TEXT,
  too_new: "This board was made by a newer Bristlenose than this app can draw. Reload the Miro board, then try again.",
};

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const input = $<HTMLInputElement>("file");
const drop = $<HTMLLabelElement>("drop");
const status = $<HTMLDivElement>("status");
const bar = $<HTMLDivElement>("bar");
const fill = $<HTMLSpanElement>("fill");
const stop = $<HTMLButtonElement>("stop");
const pasteZone = $<HTMLDivElement>("paste");
const pasteHint = $<HTMLSpanElement>("paste-hint");

let building = false;
let stopRequested = false;

function show(text: string, problem = false): void {
  status.textContent = text;
  status.classList.toggle("problem", problem);
}

function progress(done: number, total: number): void {
  fill.style.width = `${total ? Math.round((100 * done) / total) : 100}%`;
  if (!stopRequested) show(`Building the board… ${done} of ${total} quotes`);
}

async function build(text: string): Promise<void> {
  if (building) return;
  let plan: BoardPlan;
  try {
    plan = planBoard(parseBoard(text));
  } catch (e) {
    show(REFUSALS[e instanceof Refusal ? e.kind : "malformed"], true);
    return;
  }
  // Send to Miro refuses an empty selection before making anything; so does this.
  if (plan.expectedQuotes === 0) {
    show("This board file has no quotes in it, so there is nothing to draw.", true);
    return;
  }
  building = true;
  stopRequested = false;
  bar.classList.add("on");
  stop.hidden = false;
  stop.disabled = false;
  show("Finding space on the board…");
  const tally = { built: 0 };
  try {
    await draw(miro.board, plan, tally, { progress, stopRequested: () => stopRequested });
    show(summary(plan, tally.built));
  } catch (e) {
    if (e instanceof Stopped) {
      show(`Stopped after ${tally.built} of ${plan.expectedQuotes} quotes. What was drawn stays on the board.`);
    } else {
      console.error(e); // the panel says how far it got and Miro's reason; the console keeps the rest
      const reason = e instanceof Error ? e.message : String(e);
      show(reason === NOT_CONNECTED ? NOT_CONNECTED : failure(plan, tally.built, reason), true);
    }
  } finally {
    building = false;
    bar.classList.remove("on");
    stop.hidden = true;
  }
}

function send(file: File): void {
  if (file.size > MAX_FILE_BYTES) {
    show(REFUSALS.too_large, true);
    return;
  }
  const reader = new FileReader();
  reader.onload = () => void build(String(reader.result));
  reader.onerror = () => show("That file couldn't be read. Try choosing it again.", true);
  reader.readAsText(file);
}

stop.addEventListener("click", () => {
  stopRequested = true;
  stop.disabled = true;
  show("Stopping after this quote…");
});

input.addEventListener("change", () => {
  const file = input.files?.[0];
  if (file) send(file);
  input.value = "";
});

// Dropping a file onto the panel needs both of these cancelled, or the frame opens the file.
for (const type of ["dragenter", "dragover"] as const) {
  drop.addEventListener(type, (e) => {
    e.preventDefault();
    drop.classList.add("over");
  });
}
drop.addEventListener("dragleave", () => drop.classList.remove("over"));
drop.addEventListener("drop", (e) => {
  e.preventDefault();
  drop.classList.remove("over");
  const file = e.dataTransfer?.files?.[0];
  if (file) send(file);
});

// A paste reaches this panel only while the panel has the keyboard; otherwise Miro takes it and
// pastes onto the board itself (seen 9 Nov 2026: the board got a doc with the board's title, and
// the panel heard nothing). So the panel has a paste area that holds the focus, takes it when the
// panel opens, and says when a paste will land here.
const PASTE_KEY = /Mac|iPhone|iPad/.test(navigator.platform || navigator.userAgent) ? "⌘V" : "Ctrl+V";
const pasteIdle = `Click here, then press ${PASTE_KEY} to paste`;
const pasteReady = `Ready: press ${PASTE_KEY} to paste`;
pasteHint.textContent = pasteIdle;
pasteZone.addEventListener("focus", () => (pasteHint.textContent = pasteReady));
pasteZone.addEventListener("blur", () => (pasteHint.textContent = pasteIdle));
window.addEventListener("load", () => {
  window.focus();
  pasteZone.focus();
});

// A board pasted with ⌘V in this panel builds, the same as choosing the file.
document.addEventListener("paste", (e) => {
  const data = e.clipboardData;
  const text = boardTextFromClipboard(data?.getData("text/html") ?? "", data?.getData("text/plain") ?? "");
  if (!text) return;
  e.preventDefault();
  if (text.length > MAX_FILE_BYTES) {
    show(REFUSALS.too_large, true);
    return;
  }
  void build(text);
});
