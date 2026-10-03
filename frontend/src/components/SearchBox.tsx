/**
 * SearchBox — the toolbar's search field: collapsible input, token chips and a
 * suggestions list (docs/design-search.md §4–§6).
 *
 * Controlled: receives `value` (the committed query) and fires `onChange`,
 * debounced 150ms. The field shows as active once the query is long enough to
 * filter by (2 characters; utils/searchMatch.ts).
 *
 * With `combo`, it is a WAI-ARIA combobox. Tokens sit before the text as chips
 * (the meaning word, the real badge, ▾), each opening a menu of its meanings
 * and Remove. Under the input, a listbox offers the free text, people and
 * tags, each with its count. The labels come from `searchBridge.ts`, the same
 * strings the Mac field draws, so the two surfaces read alike; the keys follow
 * `searchKeys.ts`, the same decisions as the Mac field's.
 *
 * Reuses molecules/search.css.
 */

import { useCallback, useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "./Badge";
import { PersonBadge } from "./PersonBadge";
import { Tooltip } from "./Tooltip";
import { getTagBg } from "../utils/colours";
import { isActiveQuery } from "../utils/searchMatch";
import { suggestionsToWire, tokensToWire, type WireToken } from "../utils/searchBridge";
import { backspaceAction, highlightedRow, moveHighlight, tokenKey } from "../utils/searchKeys";
import type { Suggestion } from "../utils/searchSuggest";
import type { SearchToken } from "../utils/searchTokens";

/** What the field needs to be a combobox. */
export interface SearchCombo {
  tokens: SearchToken[];
  /** Suggestions for the committed query (`value`). */
  suggestions: Suggestion[];
  /** A tag's colour, as its badges on the cards have it. */
  tagColour: (name: string) => { colourSet: string; colourIndex: number } | null;
  /** A person or tag row was chosen: it becomes a token. */
  onChoose: (id: string) => void;
  onTokenMode: (token: SearchToken, mode: string) => void;
  onTokenRemove: (token: SearchToken) => void;
}

export interface SearchBoxProps {
  /** The committed search query (from store). */
  value: string;
  /** Called with the debounced query string. */
  onChange: (query: string) => void;
  /** Clear the whole search (ⓧ, Esc, collapsing): the text and any tokens.
   *  Defaults to `onChange("")`, which clears the text only. */
  onClear?: () => void;
  /** Re-read `value` whenever this changes, even if `value` did not. A typed
   *  code that becomes a token leaves an empty query, which is the value the
   *  store already held, so without it the field would go on showing "p3 ". */
  syncKey?: unknown;
  /** Tokens and suggestions; without it the field is plain text search. */
  combo?: SearchCombo;
  /** Debounce delay in ms (default 150). */
  debounce?: number;
  "data-testid"?: string;
}

const roleOf = (code: string): "participant" | "moderator" | "observer" =>
  code.startsWith("m") ? "moderator" : code.startsWith("o") ? "observer" : "participant";

export function SearchBox({
  value,
  onChange,
  onClear,
  syncKey,
  combo,
  debounce = 150,
  "data-testid": testId,
}: SearchBoxProps) {
  const { t } = useTranslation();
  const tokens = useMemo(() => combo?.tokens ?? [], [combo?.tokens]);
  const [expandedState, setExpanded] = useState(value.length > 0);
  // A field holding tokens is open, whatever opened it (a menu choice, ⌘E).
  const expanded = expandedState || tokens.length > 0;
  const [localValue, setLocalValue] = useState(value);
  const inputRef = useRef<HTMLInputElement>(null);
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const listId = useId();

  // The list is closed until the researcher types, and closes again on Esc,
  // a choice or a blur. Text the store puts back never opens it.
  const [listDismissed, setListDismissed] = useState(true);
  const [focused, setFocused] = useState(false);
  const [highlightId, setHighlightId] = useState<string | null>(null);
  /** The token a first ⌫ in the empty field selected (§6). */
  const [selectedToken, setSelectedToken] = useState<string | null>(null);
  /** The token whose meaning menu is open. */
  const [menuFor, setMenuFor] = useState<string | null>(null);

  // Sync local value when parent value changes (e.g. external clear). The
  // store echoing what was just typed is not a change: it must not close the
  // list the typing opened.
  const localRef = useRef(localValue);
  localRef.current = localValue;
  useEffect(() => {
    if (value === localRef.current) return;
    setLocalValue(value);
    if (value.length > 0) setExpanded(true);
    setListDismissed(true);
  }, [value, syncKey]);

  const rows = useMemo(
    () => (combo ? suggestionsToWire(value, combo.suggestions).rows : []),
    [combo, value],
  );
  const rowIds = rows.map((r) => r.id);
  const wireTokens = useMemo(() => tokensToWire(tokens), [tokens]);
  const highlighted = highlightedRow(highlightId, rowIds);
  const listOpen =
    combo !== undefined && focused && localValue.trim() !== "" && rows.length > 0 && !listDismissed;

  const commitValue = useCallback(
    (v: string) => {
      clearTimeout(timerRef.current);
      timerRef.current = setTimeout(() => onChange(v), debounce);
    },
    [onChange, debounce],
  );

  // Cleanup timer on unmount
  useEffect(() => () => clearTimeout(timerRef.current), []);

  // A token's menu closes on a click outside it and on Esc.
  useEffect(() => {
    if (menuFor === null) return;
    const onMouse = (e: MouseEvent) => {
      if ((e.target as Element | null)?.closest?.(".search-token-wrap.menu-open")) return;
      setMenuFor(null);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setMenuFor(null);
    };
    document.addEventListener("mousedown", onMouse);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onMouse);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuFor]);

  function handleToggle() {
    if (expanded) {
      // Collapse and clear
      setExpanded(false);
      setLocalValue("");
      clearTimeout(timerRef.current);
      clearAll();
    } else {
      setExpanded(true);
      // Focus the input after expansion
      requestAnimationFrame(() => inputRef.current?.focus());
    }
  }

  function handleInput(e: React.ChangeEvent<HTMLInputElement>) {
    const v = e.target.value;
    setLocalValue(v);
    setListDismissed(false);
    setHighlightId(null);
    setSelectedToken(null);
    commitValue(v);
  }

  function clearAll() {
    setSelectedToken(null);
    if (onClear) onClear();
    else onChange("");
  }

  function handleClear() {
    setLocalValue("");
    clearTimeout(timerRef.current);
    clearAll();
    inputRef.current?.focus();
  }

  /** Send what was typed now, without the debounce wait. */
  function commitNow() {
    clearTimeout(timerRef.current);
    if (localValue !== value) onChange(localValue);
  }

  function choose(id: string) {
    const row = rows.find((r) => r.id === id);
    if (!row || !combo) return;
    setListDismissed(true);
    setHighlightId(null);
    if (row.kind === "text") {
      commitNow();
    } else {
      // The chosen person or tag replaces what was typed to find it (§6).
      clearTimeout(timerRef.current);
      setLocalValue("");
      combo.onChoose(id);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    // An input method composing (Japanese, Chinese, Korean) owns these keys.
    if (e.nativeEvent.isComposing) return;
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      if (!combo || rows.length === 0) return;
      e.preventDefault();
      if (listOpen) setHighlightId(moveHighlight(highlighted, e.key === "ArrowDown" ? 1 : -1, rowIds));
      else if (localValue.trim() !== "") setListDismissed(false);
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (listOpen && highlighted) choose(highlighted);
      else commitNow();
      return;
    }
    if (e.key === "Backspace" && combo && !e.repeat) {
      const action = backspaceAction(localValue, tokens, selectedToken);
      if (action.kind === "select") {
        e.preventDefault();
        setSelectedToken(action.key);
      } else if (action.kind === "remove") {
        e.preventDefault();
        setSelectedToken(null);
        combo.onTokenRemove(action.token);
      }
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      if (listOpen) {
        setListDismissed(true);
      } else if (localValue || tokens.length > 0) {
        handleClear();
      } else {
        handleToggle(); // collapse
      }
    }
  }

  const containerClass = [
    "search-container",
    expanded ? "expanded" : "",
    isActiveQuery(localValue) ? "has-query" : "",
    tokens.length > 0 ? "has-tokens" : "",
  ]
    .filter(Boolean)
    .join(" ");

  const optionId = (id: string) => `${listId}-${id.replace(/[^a-zA-Z0-9_-]/g, "_")}`;

  function tokenBadge(token: SearchToken, wire: WireToken) {
    if (token.kind === "person") {
      return (
        <PersonBadge
          code={token.code}
          role={roleOf(token.code)}
          name={wire.label !== token.code ? wire.label : undefined}
        />
      );
    }
    const c = combo?.tagColour(token.name);
    return (
      <Badge text={token.name} variant="user" colour={c ? getTagBg(c.colourSet, c.colourIndex) : undefined} />
    );
  }

  function rowBadge(s: Suggestion) {
    if (s.kind === "person") {
      return <PersonBadge code={s.code} role={roleOf(s.code)} name={s.name ?? undefined} />;
    }
    if (s.kind === "tag") {
      return (
        <Badge
          text={s.tag.name}
          variant="user"
          colour={s.tag.colour_set ? getTagBg(s.tag.colour_set, s.tag.colour_index) : undefined}
        />
      );
    }
    return null;
  }

  function option(index: number) {
    const row = rows[index];
    const s = combo!.suggestions[index];
    const on = row.id === highlighted;
    return (
      // The keys are the input's: a combobox's options are reached through
      // aria-activedescendant, never focused, so they take clicks only.
      // eslint-disable-next-line jsx-a11y/click-events-have-key-events
      <li
        key={row.id}
        id={optionId(row.id)}
        role="option"
        aria-selected={on}
        className={`search-option${on ? " highlighted" : ""}`}
        // Keep the focus in the field: a mousedown would blur it first.
        onMouseDown={(e) => e.preventDefault()}
        onMouseMove={() => {
          if (!on) setHighlightId(row.id);
        }}
        onClick={() => choose(row.id)}
        data-testid={testId ? `${testId}-option-${row.kind}` : undefined}
      >
        {row.kind === "text" ? (
          <>
            <QuotesLensGlyph />
            <span className="search-option-label">{labelWithTyped(row.label, row.typed)}</span>
          </>
        ) : (
          <span className="search-option-badge">{rowBadge(s)}</span>
        )}
        <span className="search-option-count">{row.count.toLocaleString()}</span>
      </li>
    );
  }

  const peopleIdx = rows.flatMap((r, i) => (r.kind === "person" ? [i] : []));
  const tagIdx = rows.flatMap((r, i) => (r.kind === "tag" ? [i] : []));

  return (
    <div className={containerClass} data-testid={testId}>
      <Tooltip content={t("labels.search")} shortcut={{ key: "/" }}>
        <button
          type="button"
          className="search-toggle"
          onClick={handleToggle}
          aria-label={t("search.ariaLabel")}
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
      </Tooltip>
      <div className="search-field">
        {tokens.length > 0 && (
          <div className="search-tokens">
            {tokens.map((token, i) => {
              const key = tokenKey(token);
              const wire = wireTokens[i];
              const current = wire.modes.find((m) => m.id === wire.mode);
              const open = menuFor === key;
              return (
                <span key={key} className={`search-token-wrap${open ? " menu-open" : ""}`}>
                  <button
                    type="button"
                    className={`search-token${selectedToken === key ? " selected" : ""}`}
                    aria-haspopup="menu"
                    aria-expanded={open}
                    aria-label={current?.label ?? wire.label}
                    onClick={() => setMenuFor(open ? null : key)}
                    data-testid={testId ? `${testId}-token` : undefined}
                  >
                    {current?.word && <span className="search-token-word">{current.word}</span>}
                    {tokenBadge(token, wire)}
                    <svg
                      className="search-token-disclosure"
                      width="8"
                      height="8"
                      viewBox="0 0 8 8"
                      aria-hidden="true"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.4"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <path d="M1.5 3 4 5.5 6.5 3" />
                    </svg>
                  </button>
                  {open && (
                    <ul
                      className="search-token-menu"
                      role="menu"
                      data-testid={testId ? `${testId}-token-menu` : undefined}
                    >
                      {wire.modes.map((m) => (
                        <li
                          key={m.id}
                          role="menuitemradio"
                          aria-checked={m.id === wire.mode}
                          aria-disabled={!m.enabled}
                          tabIndex={m.enabled ? 0 : -1}
                          className={[m.id === wire.mode ? "active" : "", m.enabled ? "" : "disabled"]
                            .filter(Boolean)
                            .join(" ")}
                          onClick={() => {
                            if (!m.enabled) return;
                            combo!.onTokenMode(token, m.id);
                            setMenuFor(null);
                          }}
                          onKeyDown={(e) => {
                            if ((e.key === "Enter" || e.key === " ") && m.enabled) {
                              e.preventDefault();
                              combo!.onTokenMode(token, m.id);
                              setMenuFor(null);
                            }
                          }}
                        >
                          <span className="menu-icon" aria-hidden="true">
                            {m.id === wire.mode ? "✓" : " "}
                          </span>
                          {m.label}
                        </li>
                      ))}
                      <li role="separator" className="search-token-menu-separator" />
                      <li
                        role="menuitem"
                        tabIndex={0}
                        onClick={() => {
                          combo!.onTokenRemove(token);
                          setMenuFor(null);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            combo!.onTokenRemove(token);
                            setMenuFor(null);
                          }
                        }}
                      >
                        <span className="menu-icon" aria-hidden="true">
                          {" "}
                        </span>
                        {wire.removeLabel}
                      </li>
                    </ul>
                  )}
                </span>
              );
            })}
          </div>
        )}
        <input
          ref={inputRef}
          className="search-input"
          type="text"
          placeholder={t("search.placeholder")}
          autoComplete="off"
          value={localValue}
          onChange={handleInput}
          onKeyDown={handleKeyDown}
          onFocus={() => setFocused(true)}
          onBlur={() => {
            setFocused(false);
            setSelectedToken(null);
          }}
          {...(combo
            ? {
                role: "combobox",
                "aria-autocomplete": "list" as const,
                "aria-expanded": listOpen,
                "aria-controls": listId,
                "aria-activedescendant": listOpen && highlighted ? optionId(highlighted) : undefined,
              }
            : {})}
          data-testid={testId ? `${testId}-input` : undefined}
        />
        <button
          type="button"
          className="search-clear"
          onClick={handleClear}
          aria-label={t("search.clearAriaLabel")}
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
        {listOpen && (
          <ul
            id={listId}
            className="search-listbox"
            role="listbox"
            data-testid={testId ? `${testId}-listbox` : undefined}
          >
            {rows.map((r, i) => (r.kind === "text" ? option(i) : null))}
            {peopleIdx.length > 0 && (
              <li role="group" aria-label={t("search.suggest.people")} className="search-group">
                <ul role="presentation">{peopleIdx.map(option)}</ul>
              </li>
            )}
            {tagIdx.length > 0 && (
              <li role="group" aria-label={t("tags.tags")} className="search-group">
                <ul role="presentation">{tagIdx.map(option)}</ul>
              </li>
            )}
          </ul>
        )}
      </div>
    </div>
  );
}

/** The free-text row's label: what was typed in the text colour, the rest of
 *  the template muted, as the Mac row draws it (§4). */
function labelWithTyped(label: string, typed: Array<[number, number]>) {
  const out: React.ReactNode[] = [];
  let at = 0;
  for (const [s, e] of typed) {
    if (s > at) out.push(<span key={`r${at}`} className="search-option-rest">{label.slice(at, s)}</span>);
    out.push(<span key={`t${s}`} className="search-option-typed">{label.slice(s, e)}</span>);
    at = e;
  }
  if (at < label.length) out.push(<span key={`r${at}`} className="search-option-rest">{label.slice(at)}</span>);
  return out;
}

/** The Quotes lens's glyph, drawn to match its SF Symbol (`text.quote`): SF
 *  Symbols may not ship in a web page (§4). */
function QuotesLensGlyph() {
  return (
    <svg
      className="search-option-glyph"
      width="15"
      height="15"
      viewBox="0 0 16 16"
      aria-hidden="true"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
    >
      <path d="M2.5 4.5h2v2l-1 2" />
      <path d="M6 4.5h2v2l-1 2" />
      <line x1="10" y1="5" x2="14" y2="5" />
      <line x1="10" y1="8" x2="14" y2="8" />
      <line x1="2.5" y1="11.5" x2="14" y2="11.5" />
    </svg>
  );
}
