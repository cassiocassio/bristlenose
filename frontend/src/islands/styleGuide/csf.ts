/**
 * The shape every style-guide section is written in: Component Story Format
 * (CSF 3), the plain ES-module convention Storybook indexes. A default export
 * names the section; each named export is one specimen; `__namedExportsOrder`
 * fixes the order (a module namespace sorts its keys, Storybook reads this).
 *
 * No Storybook dependency: these types are the few fields we use. The owner
 * chose a specimen route over Storybook (25 Nov 2026) because the route runs
 * inside the real app shell, on `bristlenose serve` and in the Mac app's
 * webview, and Storybook rebuilds that shell as a second copy. Writing the
 * sections in CSF keeps the other door open: Storybook could index these files
 * later without a rewrite.
 *
 * The rule every specimen follows (the owner's, verbatim): "only create
 * examples that directly use the exact current codepath to the design
 * system". A specimen renders a shipped component with fixture props, or a
 * token read live from the loaded theme CSS. No copied markup, no copied CSS,
 * no inline style that fakes a state.
 */

import type { ReactNode } from "react";

export interface SpecimenMeta {
  /** Storybook-style path: "Foundations/Type". */
  title: string;
  /** One or two sentences: what this is and where it is used. */
  description?: string;
  /** What the specimen cannot show here, and where to see it instead. */
  caveat?: string;
}

export interface SpecimenStory {
  /** Display name; defaults to the export name. */
  name?: string;
  render: () => ReactNode;
}

export interface SpecimenModule {
  default: SpecimenMeta;
  __namedExportsOrder: readonly string[];
  [story: string]: unknown;
}

/** The stories of a module, in their declared order. */
export function storiesOf(mod: SpecimenModule): Array<{ key: string; story: SpecimenStory }> {
  return mod.__namedExportsOrder.map((key) => {
    const story = mod[key] as SpecimenStory | undefined;
    if (!story || typeof story.render !== "function") {
      throw new Error(`style guide: ${mod.default.title} lists "${key}" but exports no story by that name`);
    }
    return { key, story };
  });
}

/** Stable anchor id for a section ("Foundations/Type" → "foundations-type"). */
export function sectionId(meta: SpecimenMeta): string {
  return meta.title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}
