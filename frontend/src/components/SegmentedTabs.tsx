/**
 * SegmentedTabs — a few joined buttons that switch what a dialog shows: the web twin of the
 * Mac's segmented control (the Miro sheet's `Picker(.segmented)`).
 *
 * Tablist semantics, as the ARIA authoring practices give them: one tab in the tab order (the
 * selected one), ← → move and select, Home / End go to the ends. The look is `.bn-seg` in
 * `atoms/modal.css`.
 *
 * @module SegmentedTabs
 */

import { useRef } from "react";
import type { KeyboardEvent } from "react";

export interface SegmentedTab<K extends string> {
  key: K;
  label: string;
}

interface SegmentedTabsProps<K extends string> {
  tabs: ReadonlyArray<SegmentedTab<K>>;
  selected: K;
  onSelect: (key: K) => void;
  /** The id of the element that names the choice (the dialog's heading). */
  labelledBy: string;
  /** Each tab controls `${idPrefix}-panel-${key}` and is `${idPrefix}-tab-${key}`. */
  idPrefix: string;
}

export function SegmentedTabs<K extends string>({
  tabs,
  selected,
  onSelect,
  labelledBy,
  idPrefix,
}: SegmentedTabsProps<K>) {
  const refs = useRef<Array<HTMLButtonElement | null>>([]);

  const onKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    const at = tabs.findIndex((tab) => tab.key === selected);
    let next = -1;
    if (e.key === "ArrowRight") next = (at + 1) % tabs.length;
    else if (e.key === "ArrowLeft") next = (at - 1 + tabs.length) % tabs.length;
    else if (e.key === "Home") next = 0;
    else if (e.key === "End") next = tabs.length - 1;
    if (next < 0) return;
    e.preventDefault();
    e.stopPropagation(); // the report's own arrow keys must not also act
    onSelect(tabs[next].key);
    refs.current[next]?.focus();
  };

  return (
    <div className="bn-seg" role="tablist" aria-labelledby={labelledBy}>
      {tabs.map((tab, i) => {
        const on = tab.key === selected;
        return (
          <button
            key={tab.key}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={`${idPrefix}-tab-${tab.key}`}
            aria-selected={on}
            aria-controls={`${idPrefix}-panel-${tab.key}`}
            tabIndex={on ? 0 : -1}
            onClick={() => onSelect(tab.key)}
            onKeyDown={onKeyDown}
            data-testid={`${idPrefix}-tab-${tab.key}`}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}
