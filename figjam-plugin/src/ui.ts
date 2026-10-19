// The plugin panel: pick or drop a board file, then watch it build.
// Text from the file is never put into this page; status lines are set with
// textContent only.

import { MAX_FILE_BYTES, REFUSAL_TEXT } from "./board";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const input = $<HTMLInputElement>("file");
const drop = $<HTMLLabelElement>("drop");
const status = $<HTMLDivElement>("status");
const bar = $<HTMLDivElement>("bar");
const fill = $<HTMLSpanElement>("fill");
const stop = $<HTMLButtonElement>("stop");

function show(text: string, problem = false): void {
  status.textContent = text;
  status.classList.toggle("problem", problem);
}

function build(text: string): void {
  // Fonts load before the first sticky, so the count starts only once they have.
  show("Preparing the board…");
  bar.classList.add("on");
  stop.hidden = false;
  stop.disabled = false;
  parent.postMessage({ pluginMessage: { type: "build", text } }, "*");
}

function send(file: File): void {
  if (file.size > MAX_FILE_BYTES) {
    show(REFUSAL_TEXT.too_large, true);
    return;
  }
  const reader = new FileReader();
  reader.onload = () => build(String(reader.result));
  reader.onerror = () => show("That file couldn't be read. Try choosing it again.", true);
  reader.readAsText(file);
}

// Acknowledged at once; the drawing stops at its next yield and the panel closes with a summary.
stop.addEventListener("click", () => {
  stop.disabled = true;
  show("Stopping…");
  parent.postMessage({ pluginMessage: { type: "stop" } }, "*");
});

input.addEventListener("change", () => {
  const file = input.files?.[0];
  if (file) send(file);
  input.value = "";
});

// Dropping a file onto the panel needs both of these cancelled, or the
// browser frame opens the file instead.
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

// Bristlenose's Copy for FigJam puts the board on the clipboard; ⌘V in this panel
// builds it, the same as choosing the file. Only plain text is read.
document.addEventListener("paste", (e) => {
  const text = e.clipboardData?.getData("text/plain") ?? "";
  if (!text) return;
  e.preventDefault();
  if (text.length > MAX_FILE_BYTES) {
    show(REFUSAL_TEXT.too_large, true);
    return;
  }
  build(text);
});

type FromCode =
  | { type: "progress"; done: number; total: number }
  | { type: "refused"; message: string }
  | { type: "failed"; message: string };

window.onmessage = (event: MessageEvent) => {
  const msg = event.data?.pluginMessage as FromCode | undefined;
  if (!msg) return;
  if (msg.type === "progress") {
    fill.style.width = `${msg.total ? Math.round((100 * msg.done) / msg.total) : 100}%`;
    if (!stop.disabled) show(`Building the board… ${msg.done} of ${msg.total} quotes`);
  } else {
    bar.classList.remove("on");
    stop.hidden = true;
    show(msg.message, true);
  }
};
