/**
 * A count that rolls like an odometer when it changes (owner, 24 Nov 2026): only the
 * digits that changed move, up when the number grows and down when it shrinks, fast and
 * plain, so the eye catches that a count moved.
 *
 * The outgoing digit is CSS generated content (`data-from`) with empty alternative text,
 * so the element's text, and what a screen reader reads, is only ever the current value.
 * The motion is CSS (threshold-review.css, `.bn-roll-*`) and stops under reduced motion
 * or with the house animations off; a column restarts by remounting under a new key.
 */

import { useState } from "react";

export function RollingNumber({ value }: { value: number }) {
  // The value drawn last, kept in state so the change is seen during render (React's
  // "storing information from previous renders"), not an effect a frame late.
  const [shown, setShown] = useState({ value, from: value, turn: 0 });
  if (shown.value !== value) {
    setShown({ value, from: shown.value, turn: shown.turn + 1 });
  }
  const to = String(shown.value);
  const from = String(shown.from);
  if (shown.turn === 0 || to === from) return <>{to}</>;

  const width = Math.max(to.length, from.length);
  const next = to.padStart(width, " ");
  const prev = from.padStart(width, " ");
  const dir = shown.value > shown.from ? "up" : "down";
  return (
    <>
      {Array.from(next, (digit, i) =>
        digit === prev[i] ? (
          digit.trim()
        ) : (
          <span className="bn-roll-col" key={`${i}-${shown.turn}`}>
            <span className={`bn-roll-digit bn-roll-digit--${dir}`} data-from={prev[i].trim()}>
              {digit.trim()}
            </span>
          </span>
        ),
      )}
    </>
  );
}
