/**
 * Selector — generic dropdown primitive.
 *
 * Compact trigger button (label + caret) that opens a dropdown menu.
 * Each item can have a primary label and optional secondary detail line.
 * Closes on outside click, Escape, or item selection.
 *
 * Usage:
 *   <Selector
 *     label="Session 1"
 *     items={sessions}
 *     itemKey={(s) => s.id}
 *     renderItem={(s) => <><strong>Session {s.num}</strong><span>p1 Maya</span></>}
 *     activeKey={currentId}
 *     onSelect={(s) => navigate(s.id)}
 *   />
 */

import { useEffect, useRef, useState } from "react";

export interface SelectorProps<T> {
  /** Text shown on the compact trigger button. */
  label: string;
  /** Items to display in the dropdown. */
  items: T[];
  /** Unique key for each item. */
  itemKey: (item: T) => string;
  /** Render the content of each dropdown row. */
  renderItem: (item: T) => React.ReactNode;
  /** Key of the currently active/selected item (gets accent colour). */
  activeKey?: string;
  /** Called when an item is selected. If it returns a string, that string
   *  is used as an href (navigation link). Otherwise it's a callback. */
  onSelect?: (item: T) => void;
  /** If provided, items render as `<a>` with this href. Takes the item. */
  itemHref?: (item: T) => string;
  /** Optional CSS class on the outermost container. */
  className?: string;
  "data-testid"?: string;
}

export function Selector<T>({
  label,
  items,
  itemKey,
  renderItem,
  activeKey,
  onSelect,
  itemHref,
  className,
  "data-testid": testId,
}: SelectorProps<T>) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement | null>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open]);

  const containerClass = ["bn-selector", className].filter(Boolean).join(" ");

  return (
    <div className={containerClass} ref={ref} data-testid={testId}>
      <button
        type="button"
        className="bn-selector__trigger"
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        aria-haspopup="listbox"
      >
        {label}{" "}
        <span className="bn-selector__caret" aria-hidden="true">
          &#x25BE;
        </span>
      </button>
      {open && (
        <ul className="bn-selector__menu" role="listbox">
          {items.map((item) => {
            const key = itemKey(item);
            const isActive = activeKey === key;
            const itemClass = [
              "bn-selector__item",
              isActive ? "bn-selector__item--active" : "",
            ]
              .filter(Boolean)
              .join(" ");

            const content = renderItem(item);

            function handleClick() {
              setOpen(false);
              onSelect?.(item);
            }

            if (itemHref) {
              return (
                <li key={key} role="option" aria-selected={isActive}>
                  <a href={itemHref(item)} className={itemClass} onClick={handleClick}>
                    {content}
                  </a>
                </li>
              );
            }

            return (
              <li key={key} role="option" aria-selected={isActive}>
                <button type="button" className={itemClass} onClick={handleClick}>
                  {content}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
