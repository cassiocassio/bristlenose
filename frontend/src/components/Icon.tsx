/**
 * The house icons, in one place. Drawn the way NavBar and EyeToggle draw
 * theirs by hand: a 16-unit grid, a 1.4 stroke, round caps and joins, in
 * currentColor so a glyph follows the text it sits in. The stroke does not
 * scale with the box (`non-scaling-stroke`), so a glyph keeps the house weight
 * at a menu tick's size as at a toolbar's.
 *
 * The web can't use SF Symbols; the Mac app draws its own native controls with
 * them (PersonPickerPopover.swift draws the SF Symbol `checkmark`).
 *
 * Add a glyph here rather than inlining another <svg> in a component.
 */

const PATHS = {
  /** A menu's current answer: short left leg, long right leg, as a Mac menu's. */
  check: "M2 8.5 6 12.5 14 3.5",
  /** "Not this person": clears a speaker back to unknown (the person picker). */
  x: "M4.5 4.5 11.5 11.5M11.5 4.5 4.5 11.5",
} as const;

export type IconName = keyof typeof PATHS;

interface IconProps {
  name: IconName;
  /** `menu` sizes the glyph for a menu's check gutter (atoms/icon.css). */
  size?: "menu";
}

export function Icon({ name, size }: IconProps) {
  return (
    <svg
      className={`bn-icon bn-icon-${name}${size ? ` bn-icon--${size}` : ""}`}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
    >
      <path d={PATHS[name]} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
