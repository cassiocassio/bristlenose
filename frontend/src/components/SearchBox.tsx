/**
 * SearchBox — collapsible search input for the toolbar.
 *
 * Controlled component: receives `value` and fires `onChange`.
 * Debounces input by 150ms before notifying parent.
 * Matches vanilla search.js behaviour: magnifying glass toggle,
 * collapsible field, clear button, min 3 chars for activation.
 *
 * Reuses molecules/search.css (.search-container, .search-input, .search-clear).
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface SearchBoxProps {
  /** The committed search query (from store). */
  value: string;
  /** Called with the debounced query string. */
  onChange: (query: string) => void;
  /** Debounce delay in ms (default 150). */
  debounce?: number;
  "data-testid"?: string;
}

export function SearchBox({
  value,
  onChange,
  debounce = 150,
  "data-testid": testId,
}: SearchBoxProps) {
  const [expanded, setExpanded] = useState(value.length > 0);
  const [localValue, setLocalValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  // Sync local value when parent value changes (e.g. external clear)
  useEffect(() => {
    setLocalValue(value);
    if (value.length > 0) setExpanded(true);
  }, [value]);

  const commitValue = useCallback(
    (v: string) => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onChange(v), debounce);
    },
    [onChange, debounce],
  );

  // Cleanup timer on unmount
  useEffect(() => () => clearTimeout(timerRef.current), []);

  function handleToggle() {
    if (expanded) {
      // Collapse and clear
      setExpanded(false);
      setLocalValue("");
      clearTimeout(timerRef.current);
      onChange("");
    } else {
      setExpanded(true);
      // Focus the input after expansion
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setLocalValue(v);
    commitValue(v);
  }

  function handleClear() {
    setLocalValue("");
    clearTimeout(timerRef.current);
    onChange("");
    inputRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      if (localValue) {
        handleClear();
      } else {
        handleToggle(); // collapse
      }
    }
  }

  const containerClass = [
    "search-container",
    expanded ? "expanded" : "",
    localValue.length >= 3 ? "has-query" : "",
  ]
    .filter(Boolean)
    .join(" ");

  return (
    <div className={containerClass} data-testid={testId}>
      <button
        type="button"
        className="search-toggle"
        onClick={handleToggle}
        aria-label="Search quotes"
        data-testid={testId ? `${testId}-toggle` : undefined}
      >
        <svg
          width="15"
          height="15"
          viewBox="0 0 16 16"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="6.5" cy="6.5" r="5.5" />
          <line x1="10.5" y1="10.5" x2="15" y2="15" />
        </svg>
      </button>
      <div className="search-field">
        <input
          ref={inputRef}
          className="search-input"
          type="text"
          placeholder="Filter quotes\u2026"
          autoComplete="off"
          value={localValue}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          data-testid={testId ? `${testId}-input` : undefined}
        />
        <button
          type="button"
          className="search-clear"
          onClick={handleClear}
          aria-label="Clear search"
          data-testid={testId ? `${testId}-clear` : undefined}
        >
          <svg
            width="12"
            height="12"
            viewBox="0 0 12 12"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          >
            <line x1="2" y1="2" x2="10" y2="10" />
            <line x1="10" y1="2" x2="2" y2="10" />
          </svg>
        </button>
      </div>
    </div>
  );
}
