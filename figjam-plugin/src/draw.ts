// Drawing a BoardPlan in the open FigJam board — the part only Figma can do:
// how tall a sticky grew, which fonts load, where the free space is. No side
// effects on import, so it can be run without the panel.

import { type BoardPlan, type StickyPlan, rgb } from "./plan";

const GAP = 24; // between stickies, and between columns
const PAD = 40; // inside a section
const FRAME_GAP = 120; // between sections
const TITLE_GAP = 96; // from the title to the sections
// Figma's main thread repaints the panel only when the plugin yields, so the yield is what makes
// the bar move. Yielding by time rather than by a count of stickies keeps it moving evenly however
// long a quote is (a set of three parts once advanced the count three times as slowly).
const YIELD_MS = 50;
// A set's parts overlap by about one x-height and step right by the same, so
// each left edge shows a small square notch — the owner's spacing on the Miro
// board (board_layout.SET_GAP / SET_STAGGER), scaled to FigJam's 16 px type.
const NOTCH = 9;

const pause = () => new Promise<void>((resolve) => setTimeout(resolve, 1));

/** The researcher pressed Stop: thrown at the next yield, so the board keeps what was drawn. */
export class Stopped extends Error {}

interface Fonts {
  base: FontName;
  bold: FontName | null;
  italic: FontName | null;
}

export const fontState = { missing: false };

async function loadFonts(): Promise<Fonts> {
  // A new sticky's own font is the one FigJam uses (Inter Medium today); its
  // bold and italic are loaded alongside, and the board is still drawn — plain —
  // if either is missing. Every load is awaited before anything closes.
  const probe = figma.createSticky();
  const base = probe.text.fontName as FontName;
  probe.remove();
  const italicStyle = base.style === "Regular" ? "Italic" : `${base.style} Italic`;
  const tryLoad = async (font: FontName): Promise<FontName | null> => {
    try {
      await figma.loadFontAsync(font);
      return font;
    } catch {
      fontState.missing = true;
      return null;
    }
  };
  await figma.loadFontAsync(base);
  const [bold, italic] = await Promise.all([
    tryLoad({ family: base.family, style: "Bold" }),
    tryLoad({ family: base.family, style: italicStyle }),
  ]);
  return { base, bold, italic };
}

function makeSticky(p: StickyPlan, wide: boolean, fonts: Fonts): StickyNode {
  const s = figma.createSticky();
  s.authorVisible = false;
  s.isWideWidth = wide;
  s.text.characters = p.characters;
  if (p.bold && fonts.bold) s.text.setRangeFontName(p.bold[0], p.bold[1], fonts.bold);
  if (p.italic && fonts.italic) s.text.setRangeFontName(p.italic[0], p.italic[1], fonts.italic);
  if (p.small) {
    const size = s.text.fontSize;
    if (typeof size === "number") s.text.setRangeFontSize(p.small[0], p.small[1], Math.round(size * 0.8));
  }
  if (p.link) s.text.setRangeHyperlink(p.link.range[0], p.link.range[1], { type: "URL", value: p.link.url });
  s.fills = [{ type: "SOLID", color: rgb(p.fill) }];
  return s;
}

// A column's header is a short pink label, not a sticky (owner, 17 Oct 2026,
// for density): a sticky is at least 240 tall, which is a lot of pink for two
// lines. It is a FigJam shape, so — unlike a section name — it still shows in an
// image export. Shapes don't grow to fit their text, so each is measured.
const STICKY_WIDTH = { square: 240, wide: 416 };
const LABEL_INSET = 16; // room above and below the text, measured on SQUARE
const LABEL_MIN = 48;

function makeHeaderLabel(p: StickyPlan, width: number, fonts: Fonts, measure: TextNode): ShapeWithTextNode {
  const s = figma.createShapeWithText();
  s.shapeType = "SQUARE"; // ROUNDED_RECTANGLE becomes a pill at this height and insets its text further
  s.text.characters = p.characters;
  if (p.bold && fonts.bold) s.text.setRangeFontName(p.bold[0], p.bold[1], fonts.bold);
  // Left-aligned like the quotes beneath it. Not in the typings for a shape's
  // text sublayer, but FigJam honours it (measured in a board, 17 Oct 2026);
  // if a later FigJam drops it, the label is merely centred.
  try {
    (s.text as unknown as { textAlignHorizontal: string }).textAlignHorizontal = "LEFT";
  } catch {
    /* centred is fine */
  }
  s.fills = [{ type: "SOLID", color: rgb(p.fill) }];
  s.strokes = [];
  // Measure the same words, fonts and size at the label's text width.
  measure.resize(width - 2 * LABEL_INSET, measure.height);
  measure.characters = p.characters;
  measure.fontName = fonts.base;
  if (p.bold && fonts.bold) measure.setRangeFontName(p.bold[0], p.bold[1], fonts.bold);
  const size = s.text.fontSize;
  if (typeof size === "number") measure.fontSize = size;
  s.resize(width, Math.max(LABEL_MIN, Math.ceil(measure.height) + 2 * LABEL_INSET));
  return s;
}

/** Where the board goes: to the right of whatever is already on the page. */
function origin(): { x: number; y: number } {
  const nodes = figma.currentPage.children;
  if (nodes.length === 0) {
    const c = figma.viewport.center;
    return { x: Math.round(c.x), y: Math.round(c.y) };
  }
  let right = -Infinity;
  let top = Infinity;
  for (const n of nodes) {
    right = Math.max(right, n.x + n.width);
    top = Math.min(top, n.y);
  }
  return { x: Math.round(right + 400), y: Math.round(top) };
}

export async function draw(
  plan: BoardPlan,
  tally: { built: number },
  progress: () => void,
  stopRequested: () => boolean = () => false,
): Promise<void> {
  const fonts = await loadFonts();
  progress(); // fonts loaded: the count starts, at 0 of N
  const at = origin();
  const made: SceneNode[] = [];

  const title = figma.createText();
  title.fontName = fonts.bold ?? fonts.base;
  title.fontSize = 48;
  title.characters = plan.title;
  title.x = at.x;
  title.y = at.y;
  made.push(title);

  const measure = figma.createText();
  measure.fontName = fonts.base;
  measure.textAutoResize = "HEIGHT";
  measure.visible = false;

  try {
    let lastYield = Date.now();
    let x = at.x;
    const top = at.y + title.height + TITLE_GAP;

    for (const frame of plan.frames) {
      const section = figma.createSection();
      section.name = frame.title;
      section.x = x;
      section.y = top;
      made.push(section);

      let colX = PAD;
      let bottom = PAD;
      for (const column of frame.columns) {
        const header = makeHeaderLabel(column.header, plan.wide ? STICKY_WIDTH.wide : STICKY_WIDTH.square, fonts, measure);
        section.appendChild(header); // then local coordinates
        header.x = colX;
        header.y = PAD;
        let y = PAD + header.height + GAP;
        let width = header.width;
        for (const set of column.quotes) {
          const stickies: StickyNode[] = [];
          set.parts.forEach((p, k) => {
            const s = makeSticky(p, plan.wide, fonts);
            section.appendChild(s);
            s.x = colX + k * NOTCH;
            s.y = y;
            y += s.height - NOTCH; // stacked by the height it actually grew to
            width = Math.max(width, s.width + k * NOTCH);
            stickies.push(s);
          });
          y += NOTCH + GAP;
          // A set moves and sorts as one; ⌘-click still picks out a single part
          // to delete, which is how researchers trim (design doc, 17 Oct 2026).
          if (stickies.length > 1) figma.group(stickies, section).name = set.name;
          tally.built++;
          if (Date.now() - lastYield >= YIELD_MS) {
            progress();
            await pause();
            lastYield = Date.now();
            if (stopRequested()) throw new Stopped();
          }
        }
        bottom = Math.max(bottom, y - GAP);
        colX += width + GAP;
      }
      // Sections don't grow to fit; size this one to what it now holds.
      section.resizeWithoutConstraints(Math.max(colX - GAP + PAD, 200), bottom + PAD);
      x += section.width + FRAME_GAP;
    }
  } finally {
    measure.remove(); // even if the build stops part-way
  }

  progress();
  figma.viewport.scrollAndZoomIntoView(made);
}
