// Drawing a BoardPlan in the open FigJam board — the part only Figma can do:
// how tall a sticky grew, which fonts load, where the free space is. No side
// effects on import, so it can be run without the panel.

import { type BoardPlan, type StickyPlan, rgb } from "./plan";

const GAP = 24; // between stickies, and between columns
const PAD = 40; // inside a section
const FRAME_GAP = 120; // between sections
const TITLE_GAP = 96; // from the title to the sections
const BATCH = 40; // stickies per batch before yielding

const pause = () => new Promise<void>((resolve) => setTimeout(resolve, 1));

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

export async function draw(plan: BoardPlan, tally: { built: number }, progress: () => void): Promise<void> {
  const fonts = await loadFonts();
  const at = origin();
  const made: SceneNode[] = [];

  const title = figma.createText();
  title.fontName = fonts.bold ?? fonts.base;
  title.fontSize = 48;
  title.characters = plan.title;
  title.x = at.x;
  title.y = at.y;
  made.push(title);

  let sinceYield = 0;
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
    let width = 0;
    for (const column of frame.columns) {
      let y = PAD;
      for (const p of [column.header, ...column.quotes]) {
        const s = makeSticky(p, plan.wide, fonts);
        section.appendChild(s); // then local coordinates
        s.x = colX;
        s.y = y;
        y += s.height + GAP; // stacked by the height it actually grew to
        width = s.width;
        if (p !== column.header) tally.built++;
        if (++sinceYield >= BATCH) {
          sinceYield = 0;
          progress();
          await pause();
        }
      }
      bottom = Math.max(bottom, y - GAP);
      colX += width + GAP;
    }
    // Sections don't grow to fit; size this one to what it now holds.
    section.resizeWithoutConstraints(Math.max(colX - GAP + PAD, 200), bottom + PAD);
    x += section.width + FRAME_GAP;
  }

  progress();
  figma.viewport.scrollAndZoomIntoView(made);
}
