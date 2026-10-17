/**
 * One entry of the transcript's gutter and margin: a mark in the gutter (a link into a lens)
 * and, beside it, what the margin says about it (docs/design-transcript-gutter.md).
 *
 * The mark and the margin's title are the links; the transcript's text never is (a click
 * there is the caret). `target` pairs the entry with what it points at in the text, so
 * hovering either lights the other (useGutterHover).
 */
import type { MouseEvent, ReactNode } from "react";
import { Icon, type IconName } from "../../components/Icon";

interface GutterEntryProps {
  icon: IconName;
  /** The mark's accessible name and tooltip: the lens and where it leads ("Quotes: Delivery"). */
  name: string;
  /** Where the mark leads; without one the mark is drawn but is not a link. */
  href?: string;
  onFollow?: (e: MouseEvent) => void;
  /** The researcher hid what it names: drawn in grey. */
  hidden?: boolean;
  /** What it points at in the text, for the hover keyline: `q:<dom_id>`. */
  target: string;
  children?: ReactNode;
  "data-testid"?: string;
}

export function GutterEntry({
  icon, name, href, onFollow, hidden, target, children, "data-testid": testId,
}: GutterEntryProps) {
  return (
    <div className="bn-gutter-entry" data-hidden={hidden ? "" : undefined} data-target={target} data-testid={testId}>
      {href ? (
        <a className="bn-gutter-mark" href={href} onClick={onFollow} aria-label={name} title={name}>
          <Icon name={icon} decorative />
        </a>
      ) : (
        <span className="bn-gutter-mark">
          <Icon name={icon} label={name} />
        </span>
      )}
      <div className="bn-gutter-content">{children}</div>
    </div>
  );
}
