/**
 * The house icons, in one place: Lucide (lucide.dev, ISC), never drawn here.
 * docs/design-icon-system.md is the plan; its concept map is this file's
 * vocabulary, so components ask for a concept ("close"), not a glyph ("x"),
 * and a concept changes glyph in one line below.
 *
 * Stroke is the stem of the text the icon sits in, never under 1 px:
 * atoms/icon.css sets `stroke-width: max(1px, calc(var(--bn-icon-stem) * 1em))`,
 * which beats the stroke-width attribute below, and `nonScalingStroke` keeps
 * that width in screen pixels at any icon size. A context set in a heavier
 * weight sets `--bn-icon-stem` beside its `font-weight`.
 *
 * The attribute is a fallback, not the design: serve and the HTML export use a
 * project's baked copy of the theme CSS when it has one, and a project rendered
 * before the stem rule existed would otherwise draw Lucide's default 2 px.
 *
 * The web can't use SF Symbols; the Mac app draws its own native controls with
 * them (PersonPickerPopover.swift draws the SF Symbol `checkmark`).
 *
 * Every icon is labelled or declared decorative — the props type will not
 * compile otherwise, because Lucide hides an unlabelled icon from assistive
 * technology without complaint.
 *
 * Add a concept here rather than inlining another <svg> in a component.
 */
import {
  AppWindowMac,
  Check, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, CircleHelp, CircleX, Download,
  ExternalLink, Eye, EyeOff, Folder, LayoutGrid, List, Minus, Moon, Pencil, Play, Plus,
  RotateCcw, RotateCw, Search, Settings, SlidersHorizontal, Sparkle, Tag, TextQuote,
  TriangleAlert, Undo2, X, ZoomIn, ZoomOut, type LucideIcon,
} from "lucide-react";

const ICONS = {
  /** A menu's current answer; accept. */
  check: Check,
  /** Close, dismiss, delete a chip; "not this person" in the person picker. */
  close: X,
  /** A disclosure, closed; CSS rotates it 90° when open. Was a filled triangle in
   *  the tag sidebar — the chevron is what the macOS sidebar draws. */
  disclose: ChevronRight,
  /** The caret on a button that opens a menu. */
  caret: ChevronDown,
  /** Collapse, or step up. */
  collapse: ChevronUp,
  previous: ChevronLeft,
  next: ChevronRight,
  show: Eye,
  hide: EyeOff,
  search: Search,
  zoomIn: ZoomIn,
  zoomOut: ZoomOut,
  edit: Pencil,
  refresh: RotateCw,
  /** Export (pick, 15 Oct 2026: download over share). */
  export: Download,
  folder: Folder,
  tag: Tag,
  /** The contents rail: a bulleted list. */
  contents: List,
  heatmap: LayoutGrid,
  /** The Quotes lens; matches the Mac's SF Symbol `text.quote`. */
  quotes: TextQuote,
  /** The Screens lens; stands in for the Mac's SF Symbol `macwindow.on.rectangle` (Lucide has
   *  no window over a rectangle: its nearest is one window). */
  screens: AppWindowMac,
  /** Focus mode: the moon, as Mail's View menu. */
  focus: Moon,
  /** Settings (pick: the gear, over settings-2's sliders). */
  settings: Settings,
  /** Help (pick: circle-help, over info). */
  help: CircleHelp,
  /** Undo a quote edit; restore deleted tags. */
  revert: Undo2,
  /** A link that leaves the report. */
  external: ExternalLink,
  /** Add a group, a tag. */
  add: Plus,
  play: Play,
  /** An activity that partly finished. */
  warning: TriangleAlert,
  /** An activity that failed or was cancelled. */
  failed: CircleX,
  /** The AutoCode dialogs' title ornament (pick: Lucide sparkle over keeping ✦). */
  ai: Sparkle,
  /** Dev-only playground controls. */
  playground: SlidersHorizontal,
  minus: Minus,
  reset: RotateCcw,
} satisfies Record<string, LucideIcon>;

export type IconName = keyof typeof ICONS;

type IconA11y =
  /** The icon carries meaning nothing else states: it becomes the accessible name. */
  | { label: string; decorative?: never }
  /** The control around it is already named (aria-label, visible text). */
  | { decorative: true; label?: never };

export type IconProps = IconA11y & {
  name: IconName;
  /** `menu` sizes the glyph for a menu's check gutter (atoms/icon.css). */
  size?: "menu";
  /** A fixed box in CSS px, where the control was built around one. Without
   *  it the box is 1em, unless a contextual rule sizes the svg. The stroke
   *  follows the text either way. */
  px?: number;
  className?: string;
};

/** Roughly the stem of 13 px normal text; only seen where the CSS is stale. */
const FALLBACK_STROKE = 1.25;

export function Icon({ name, size, px, className, label, decorative }: IconProps) {
  const Glyph = ICONS[name];
  if (import.meta.env.DEV && !decorative && !label?.trim()) {
    console.error(`Icon "${name}": an empty label names nothing — pass a label or \`decorative\``);
  }
  const classes = ["bn-icon", `bn-icon-${name}`, size && `bn-icon--${size}`, px && "bn-icon--px", className]
    .filter(Boolean)
    .join(" ");
  return (
    <Glyph
      className={classes}
      nonScalingStroke
      strokeWidth={FALLBACK_STROKE}
      // 1em as an attribute too, so a page whose theme CSS predates atoms/icon.css
      // (serve and export prefer a project's baked copy) still draws a text-sized icon.
      size={px ?? "1em"}
      focusable="false"
      {...(decorative ? { "aria-hidden": true } : { role: "img", "aria-label": label })}
    />
  );
}
