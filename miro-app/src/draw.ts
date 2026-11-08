// Drawing a BoardPlan in the open Miro board — the only part that needs Miro.
//
// Kept thin: every decision about what goes where is in layout.ts, which is tested against
// Send to Miro's own layout. This finds free space, makes the calls in board order, groups each
// split quote, and says how far it got. The board API is passed in, so it is tested with a fake.

import type { BoardPlan } from "./layout";

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** The slice of Miro's Web SDK (`miro.board`) this app uses. */
export interface BoardApi {
  createFrame(props: Record<string, unknown>): Promise<object>;
  createText(props: Record<string, unknown>): Promise<object>;
  createStickyNote(props: Record<string, unknown>): Promise<object>;
  group(props: { items: object[] }): Promise<object>;
  findEmptySpace(props: Rect & { offset?: number }): Promise<Rect>;
  viewport: {
    get(): Promise<Rect>;
    zoomTo(items: object | object[]): Promise<unknown>;
  };
}

/** The researcher pressed Stop: thrown between quotes, so the board keeps what was drawn. */
export class Stopped extends Error {}

/** Waits before the second and third try of a refused call (Miro limits about 2,000 items a minute). */
export const RETRY_DELAYS_MS = [2000, 6000];

const FRAME_TITLE_MAX = 255; // as miro_client.create_frame sends it

export interface DrawOptions {
  progress: (done: number, total: number) => void;
  stopRequested?: () => boolean;
  sleep?: (ms: number) => Promise<void>;
  firstAnswerMs?: number;
}

/** How long the first call may take before the panel says Miro isn't answering. Miro's loader
 * turns a failed connection into a promise that never settles (seen 8 Nov 2026 with the page open
 * outside Miro: the panel sat at "Finding space on the board…" for good), so without this a
 * researcher would watch that line forever. */
export const FIRST_ANSWER_MS = 15000;

export const NOT_CONNECTED = "Miro didn't answer, so the app couldn't reach this board. Close the panel and open it again.";

function withLimit<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(NOT_CONNECTED)), ms);
    p.then(
      (v) => (clearTimeout(timer), resolve(v)),
      (e) => (clearTimeout(timer), reject(e)),
    );
  });
}

/** A refusal worth waiting out: a rate limit or a timeout. Anything else (the SDK not connected,
 * content Miro won't take) is said at once rather than retried into a long, misleading wait. */
export function isTransient(e: unknown): boolean {
  const text = e instanceof Error ? `${e.name} ${e.message}` : String(e);
  return /rate|limit|429|too many|timed? ?out|timeout|temporar/i.test(text);
}

async function attempt<T>(call: () => Promise<T>, sleep: (ms: number) => Promise<void>, stop: () => boolean): Promise<T> {
  for (let k = 0; ; k++) {
    try {
      return await call();
    } catch (e) {
      if (k >= RETRY_DELAYS_MS.length || !isTransient(e)) throw e;
      if (stop()) throw new Stopped();
      await sleep(RETRY_DELAYS_MS[k]);
    }
  }
}

/** Draws the plan. Resolves with the number of quotes drawn; throws Stopped or the failure. */
export async function draw(board: BoardApi, plan: BoardPlan, tally: { built: number }, opts: DrawOptions): Promise<void> {
  const sleep = opts.sleep ?? ((ms) => new Promise<void>((resolve) => setTimeout(resolve, ms)));
  const stop = opts.stopRequested ?? (() => false);
  const call = <T>(fn: () => Promise<T>) => attempt(fn, sleep, stop);

  // Somewhere free near what the researcher is looking at. Miro answers with a centre.
  const view = await withLimit(board.viewport.get(), opts.firstAnswerMs ?? FIRST_ANSWER_MS);
  const space = await call(() =>
    board.findEmptySpace({
      x: view.x + view.width / 2,
      y: view.y + view.height / 2,
      width: plan.width,
      height: plan.height,
      offset: 200,
    }),
  );
  const ox = space.x - plan.width / 2;
  const oy = space.y - plan.height / 2;

  const made: object[] = [];
  const finish = async () => {
    if (made.length) await board.viewport.zoomTo(made).catch(() => undefined);
  };
  opts.progress(0, plan.expectedQuotes);

  try {
    for (const f of plan.frames) {
      made.push(
        await call(() =>
          board.createFrame({
            title: f.title.slice(0, FRAME_TITLE_MAX),
            x: ox + f.x + f.width / 2,
            y: oy + f.y + f.height / 2,
            width: f.width,
            height: f.height,
          }),
        ),
      );
    }
    const t = plan.title;
    await call(() =>
      board.createText({ content: t.content, x: ox + t.x, y: oy + t.y, width: t.width, style: { fontSize: t.fontSize } }),
    );

    let set: object[] = [];
    for (const s of plan.stickies) {
      const item = await call(() =>
        board.createStickyNote({
          content: s.content,
          shape: plan.shape,
          style: { fillColor: s.colour },
          x: ox + s.x + s.width / 2,
          y: oy + s.y + s.height / 2,
          width: s.width,
        }),
      );
      if (s.set !== null) set.push(item);
      if (!s.last) continue;
      // A split quote's parts move as one; ⌘-click still picks out a single part to delete.
      if (set.length > 1) {
        const items = set;
        await call(() => board.group({ items }));
      }
      set = [];
      tally.built++;
      opts.progress(tally.built, plan.expectedQuotes);
      if (stop()) throw new Stopped();
    }
  } catch (e) {
    await finish(); // show what was drawn
    throw e;
  }
  await finish();
}
