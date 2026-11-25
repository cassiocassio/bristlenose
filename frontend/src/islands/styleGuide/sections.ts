/**
 * The style guide's sections, in reading order: foundations, then atoms.
 * (Owner's order, 25 Nov 2026: foundations → atoms → quote card → organisms.
 * Tags are drawn by /report/tag-specimen, which the page links to.)
 *
 * Add a section by writing a `*.stories.tsx` module in CSF (see `csf.ts`) and
 * listing it here. Storybook, if it is ever added, would index the same files.
 */

import type { SpecimenModule } from "./csf";
import * as Type from "./foundations/Type.stories";
import * as Colour from "./foundations/Colour.stories";
import * as SpaceRadius from "./foundations/SpaceRadius.stories";
import * as PersonBadge from "./atoms/PersonBadge.stories";
import * as Buttons from "./atoms/Buttons.stories";
import * as Icons from "./atoms/Icons.stories";
import * as Feedback from "./atoms/Feedback.stories";
import * as DataViz from "./atoms/DataViz.stories";
import * as Controls from "./atoms/Controls.stories";

export const SECTIONS: readonly SpecimenModule[] = [
  Type,
  Colour,
  SpaceRadius,
  PersonBadge,
  Buttons,
  Icons,
  Feedback,
  DataViz,
  Controls,
];

/** Other specimen pages in the same family, drawn from real components too. */
export const SIBLING_PAGES = [
  { href: "/report/tag-specimen", label: "Tag specimen", note: "every tag kind and state, in every context that draws one" },
  { href: "/report/picker-specimen", label: "Picker specimen", note: "the person picker on fixture names" },
  { href: "/report/specimen", label: "Grid specimen", note: "the layout frame, measured" },
] as const;
