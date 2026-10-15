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
import { Check, X, type LucideIcon } from "lucide-react";

const ICONS = {
  /** A menu's current answer; accept. */
  check: Check,
  /** Close, dismiss, delete a chip; "not this person" in the person picker. */
  close: X,
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
  className?: string;
};

/** Roughly the stem of 13 px normal text; only seen where the CSS is stale. */
const FALLBACK_STROKE = 1.25;

export function Icon({ name, size, className, label, decorative }: IconProps) {
  const Glyph = ICONS[name];
  if (import.meta.env.DEV && !decorative && !label?.trim()) {
    console.error(`Icon "${name}": an empty label names nothing — pass a label or \`decorative\``);
  }
  const classes = ["bn-icon", `bn-icon-${name}`, size && `bn-icon--${size}`, className]
    .filter(Boolean)
    .join(" ");
  return (
    <Glyph
      className={classes}
      nonScalingStroke
      strokeWidth={FALLBACK_STROKE}
      focusable="false"
      {...(decorative ? { "aria-hidden": true } : { role: "img", "aria-label": label })}
    />
  );
}
