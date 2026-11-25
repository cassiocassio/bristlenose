/**
 * Atoms / Icons — every concept in `components/Icon.tsx`, drawn by `<Icon>`.
 *
 * The list below is typed `Record<IconName, true>`, so adding a concept to
 * Icon.tsx without adding it here fails `tsc` (and the build): the gallery
 * cannot quietly fall behind the component.
 */

import { Icon, type IconName } from "../../../components/Icon";
import { Tooltip } from "../../../components/Tooltip";
import { ToolbarButton } from "../../../components/ToolbarButton";
import type { SpecimenMeta, SpecimenStory } from "../csf";

export default {
  title: "Atoms/Icons and tooltip",
  description:
    "The house icon concepts (Lucide, atoms/icon.css), at the text size they sit in, and the shared Tooltip (atoms/tooltip.css).",
  caveat: "The tooltip shows on hover or focus after its delay, as in the app: point at the button.",
} satisfies SpecimenMeta;

export const __namedExportsOrder = ["Gallery", "Sizes", "TooltipShortcut"] as const;

const ALL: Record<IconName, true> = {
  check: true, close: true, disclose: true, caret: true, collapse: true, previous: true, next: true,
  show: true, hide: true, search: true, zoomIn: true, zoomOut: true, edit: true, refresh: true,
  export: true, folder: true, tag: true, contents: true, heatmap: true, quotes: true, screens: true,
  discussion: true, timeline: true, focus: true, display: true, layoutColumns: true, layoutSingle: true,
  densityCompact: true, densityNormal: true, densitySpacious: true, settings: true, help: true,
  revert: true, external: true, add: true, play: true, success: true, info: true, warning: true,
  failed: true, broken: true, ai: true, pinned: true, playground: true, minus: true, reset: true,
};

// Not exported: in CSF every named export is a story.
const ICON_NAMES = Object.keys(ALL) as IconName[];

export const Gallery: SpecimenStory = {
  name: "Every concept",
  render: () => (
    <div className="bn-sg-swatches">
      {ICON_NAMES.map((name) => (
        <div key={name} className="bn-sg-swatch bn-sg-icon" data-testid={`bn-sg-icon-${name}`}>
          <Icon name={name} px={20} label={name} />
          <code className="bn-sg-token">{name}</code>
        </div>
      ))}
    </div>
  ),
};

export const Sizes: SpecimenStory = {
  name: "Sizes: 1em in label, body and heading text",
  render: () => (
    <div className="bn-sg-specimens">
      <span style={{ fontSize: "var(--bn-text-label)" }}>
        <Icon name="search" decorative /> label
      </span>
      <span style={{ fontSize: "var(--bn-text-body)" }}>
        <Icon name="search" decorative /> body
      </span>
      <span style={{ fontSize: "var(--bn-text-heading)" }}>
        <Icon name="search" decorative /> heading
      </span>
    </div>
  ),
};

export const TooltipShortcut: SpecimenStory = {
  name: "Tooltip, plain and with a shortcut",
  render: () => (
    <div className="bn-sg-specimens">
      <Tooltip content="Refresh the report">
        <ToolbarButton label="Refresh" icon={<Icon name="refresh" px={14} decorative />} />
      </Tooltip>
      <Tooltip content="Search quotes" shortcut={{ key: "/" }}>
        <ToolbarButton label="Search" icon={<Icon name="search" px={14} decorative />} />
      </Tooltip>
      <Tooltip content="Contents" shortcut={{ key: "[", modifier: "cmd" }}>
        <ToolbarButton label="Contents" icon={<Icon name="contents" px={14} decorative />} />
      </Tooltip>
    </div>
  ),
};
