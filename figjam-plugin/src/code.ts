// The Figma side: turns a BoardPlan into sections and stickies in the open board.
//
// Kept thin on purpose — every decision about what to draw is in plan.ts, which
// is tested. What lives here is what only Figma can answer: how tall a sticky
// grew, which fonts load, where the free space on the canvas is.
//
// Runs on Figma's main thread with no timeout, so drawing yields every ~50 ms;
// the panel shows progress meanwhile, and Stop is read at each yield. By default
// one undo reverts the whole build, which is what a researcher wants, so this
// never calls commitUndo().

import { REFUSAL_TEXT, Refusal, parseBoard } from "./board";
import { Stopped, draw, fontState } from "./draw";
import { type BoardPlan, planBoard } from "./plan";

type ToUi =
  | { type: "progress"; done: number; total: number }
  | { type: "refused"; message: string }
  | { type: "failed"; message: string };

const say = (msg: ToUi) => figma.ui.postMessage(msg);

figma.showUI(__html__, { width: 320, height: 300, themeColors: true });

let building = false;
// Set by the panel's Stop; read by the drawing loop at its next yield.
let stopRequested = false;

figma.ui.onmessage = (msg: { type: string; text?: string }) => {
  if (msg.type === "build" && typeof msg.text === "string") void start(msg.text);
  if (msg.type === "stop") stopRequested = true;
};

// A board file dropped on the canvas while the panel is open. Only a .json is
// claimed; anything else is left to FigJam.
figma.on("drop", (event: DropEvent) => {
  const file = event.files.find((f) => f.name.toLowerCase().endsWith(".json"));
  if (!file) return true;
  void file.getTextAsync().then(start);
  return false;
});

async function start(text: string): Promise<void> {
  if (building) return;
  let plan: BoardPlan;
  try {
    plan = planBoard(parseBoard(text));
  } catch (e) {
    const kind = e instanceof Refusal ? e.kind : "malformed";
    say({ type: "refused", message: REFUSAL_TEXT[kind] });
    return;
  }
  building = true;
  stopRequested = false;
  // Counted as each quote is drawn, so a failure part-way says how far it got.
  const tally = { built: 0 };
  try {
    await draw(
      plan,
      tally,
      () => say({ type: "progress", done: tally.built, total: plan.expectedQuotes }),
      () => stopRequested,
    );
  } catch (e) {
    building = false;
    if (e instanceof Stopped) {
      figma.closePlugin(`Stopped after ${tally.built} of ${plan.expectedQuotes} quotes. Undo removes what was drawn.`);
      return;
    }
    console.error(e); // the panel says how far it got; the console keeps why
    say({
      type: "failed",
      message: `Stopped after ${tally.built} of ${plan.expectedQuotes} quotes. Undo removes what was drawn; then try again.`,
    });
    return;
  }
  figma.closePlugin(summary(plan, tally.built));
}

/** What the researcher reads when the panel closes. Never "done" for a partial board. */
function summary(plan: BoardPlan, built: number): string {
  const parts = [
    built === plan.expectedQuotes
      ? `Board built: ${built} ${built === 1 ? "quote" : "quotes"}.`
      : `Built ${built} of ${plan.expectedQuotes} quotes — some are missing.`,
  ];
  if (fontState.missing) parts.push("Some text styles weren't available, so italics or bold may be missing.");
  if (plan.droppedLinks) parts.push(`${plan.droppedLinks} clip links weren't web addresses and were left out.`);
  return parts.join(" ");
}
