/**
 * SignalsSidebar — signal-entry navigation for the Analysis tab left sidebar.
 *
 * One run of locations, ranked by their strongest signal, cards ranked within.
 * Clicking an entry focuses the signal card and syncs the inspector panel.
 *
 * It used to group by KIND — Sentiment then Codebooks, each split again into
 * Section and Theme, four sub-headings. Location organises it now, because the
 * researcher's job is holistic: everything needed to fix Shopping Bag belongs
 * in one place, so the fixes can be considered together. Sections and themes
 * interleave unlabelled; the words carry it, and the Quotes lens still owns the
 * demarcation for anyone whose mental model runs on that split.
 *
 * The list comes from SignalStore, which SignalsPage fills with the
 * de-duplicated cards it renders — so the navigation is one-to-one with the
 * main content: every row lands on a card, and no card is unreachable.
 *
 * @module SignalsSidebar
 */

import { Fragment, useCallback } from "react";
import {
  useSignalStore,
  setFocusedSignalKey,
} from "../contexts/SignalStore";
import { getGroupBg } from "../utils/colours";
import { groupSignalsByLocation } from "../utils/signalDedup";
import type { UnifiedSignal } from "../utils/types";

// ── Component ────────────────────────────────────────────────────────

export function SignalsSidebar() {
  const { signals, focusedKey } = useSignalStore();

  const handleClick = useCallback((key: string) => {
    setFocusedSignalKey(key);
    window.dispatchEvent(
      new CustomEvent("bn:signal-focus", { detail: { key } }),
    );
  }, []);

  if (signals.length === 0) return null;

  // No wrapper: SidebarLayout already mounts this inside `.toc-sidebar-body`,
  // and a second one nested the panel's side padding twice — the Signals rows
  // sat 0.85rem further in than the Codebooks rows in the same column.
  return (
    <>
      {groupSignalsByLocation(signals).map(({ location, cards }) => (
        <Fragment key={location}>
          <div className="toc-sub-heading">{location}</div>
          {cards.map((s) => (
            <SignalEntry
              key={s.key}
              signal={s}
              active={focusedKey === s.key}
              onClick={handleClick}
            />
          ))}
        </Fragment>
      ))}
    </>
  );
}

interface SignalEntryProps {
  signal: UnifiedSignal;
  active: boolean;
  onClick: (key: string) => void;
}

function SignalEntry({ signal, active, onClick }: SignalEntryProps) {
  const badgeStyle = signal.colourSet
    ? { backgroundColor: getGroupBg(signal.colourSet) }
    : undefined;
  const badgeClass = signal.colourSet
    ? "badge"
    : `badge badge-${signal.columnLabel}`;

  // A card with no elaborated name shows its group chip and nothing else. It
  // used to fall back to the location, which the heading above has already
  // said. Measured after de-duplication over 60 locations: 38 carry a single
  // named row and 13 a single bare chip, so the bare case is 22% and reads as
  // what it is — a place with one group under it. The row is still clickable
  // and still lands on a real card; the card says the rest.
  const name = signal.signalName || null;

  return (
    // Link-styled action; keyboard-accessible via role/tabIndex/onKeyDown.
    // eslint-disable-next-line jsx-a11y/anchor-is-valid
    <a
      className={`signal-entry${active ? " active" : ""}`}
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.preventDefault();
        onClick(signal.key);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick(signal.key);
        }
      }}
    >
      {name && (
        <span className="signal-entry-name" title={name}>
          {name}
        </span>
      )}
      <span className={badgeClass} style={badgeStyle}>
        {signal.columnLabel}
      </span>
    </a>
  );
}
