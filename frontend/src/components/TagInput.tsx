import { useState, useRef, useMemo, useEffect, useCallback } from "react";
import { getTagBg, getGroupBg } from "../utils/colours";

/** Small closed-eye icon shown next to autocomplete suggestions whose codebook group is hidden. */
const EyeClosedIcon = (
  <svg
    className="tag-suggest-hidden-icon"
    width="12"
    height="12"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    aria-hidden="true"
  >
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
);

/** A codebook group with its tags, used for structured autocomplete. */
export interface TagVocabularyGroup {
  groupName: string;
  colourSet: string;
  tags: { name: string; colourIndex: number }[];
}

/** A single row in the filtered suggestion list (either a group header or a tag). */
interface SuggestRow {
  type: "header" | "tag";
  groupName: string;
  colourSet: string;
  /** Tag name (only for type=tag). */
  tagName?: string;
  /** Colour index within the group (only for type=tag). */
  colourIndex?: number;
}

interface TagInputProps {
  /** All known tag names for auto-suggest (flat list — backward compat). */
  vocabulary: string[];
  /** Structured vocabulary with group metadata. When provided, takes precedence over vocabulary. */
  groupedVocabulary?: TagVocabularyGroup[];
  /** Tags to exclude from suggestions (already on this target). */
  exclude?: string[];
  /** Lowercased tag names whose codebook groups are currently hidden (eye-toggled off). */
  hiddenTags?: Set<string>;
  /** Called when user commits a tag (Enter, suggestion click, blur with non-empty). */
  onCommit: (tagName: string) => void;
  /** Called when user cancels (Escape, blur with empty). */
  onCancel: () => void;
  /** Called on Tab commit — consumer handles unmount→remount for rapid entry. */
  onCommitAndReopen?: (tagName: string) => void;
  /** Placeholder text. */
  placeholder?: string;
  /** Maximum suggestions shown in dropdown. */
  maxSuggestions?: number;
  className?: string;
  "data-testid"?: string;
}

export function TagInput({
  vocabulary,
  groupedVocabulary,
  exclude,
  hiddenTags,
  onCommit,
  onCancel,
  onCommitAndReopen,
  placeholder = "tag",
  maxSuggestions = 8,
  className,
  "data-testid": testId,
}: TagInputProps) {
  const [inputValue, setInputValue] = useState("");
  const [suggestIndex, setSuggestIndex] = useState(-1);
  const inputRef = useRef<HTMLInputElement>(null);
  const boxRef = useRef<HTMLSpanElement>(null);
  const sizerRef = useRef<HTMLSpanElement>(null);
  const mountedRef = useRef(true);

  // Auto-focus on mount.
  useEffect(() => {
    inputRef.current?.focus();
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // ── Build flat filtered list (backward compat, used for ghost text + resolveValue) ──

  const filtered = useMemo(() => {
    const val = inputValue.trim().toLowerCase();
    if (!val) return [];
    const excSet = new Set((exclude ?? []).map((e) => e.toLowerCase()));
    return vocabulary
      .filter((name) => {
        const lower = name.toLowerCase();
        return lower.includes(val) && lower !== val && !excSet.has(lower);
      })
      .slice(0, maxSuggestions);
  }, [inputValue, vocabulary, exclude, maxSuggestions]);

  // ── Build grouped suggestion rows ──────────────────────────────────────

  const suggestRows = useMemo((): SuggestRow[] => {
    if (!groupedVocabulary || groupedVocabulary.length === 0) {
      // Flat mode: no headers, just tag rows.
      return filtered.map((name) => ({
        type: "tag" as const,
        groupName: "",
        colourSet: "",
        tagName: name,
        colourIndex: 0,
      }));
    }

    const val = inputValue.trim().toLowerCase();
    if (!val) return [];
    const excSet = new Set((exclude ?? []).map((e) => e.toLowerCase()));

    const rows: SuggestRow[] = [];
    let tagCount = 0;

    for (const group of groupedVocabulary) {
      const groupNameMatches = group.groupName.toLowerCase().includes(val);

      const matchingTags = group.tags.filter((t) => {
        const lower = t.name.toLowerCase();
        // Show tag if: tag name matches OR group name matches (show all tags in group).
        const matches = lower.includes(val) || groupNameMatches;
        return matches && lower !== val && !excSet.has(lower);
      });

      if (matchingTags.length === 0) continue;
      if (tagCount >= maxSuggestions) break;

      // Add group header.
      rows.push({
        type: "header",
        groupName: group.groupName,
        colourSet: group.colourSet,
      });

      // Add tag rows (up to remaining budget).
      const budget = maxSuggestions - tagCount;
      const tagsToShow = matchingTags.slice(0, budget);
      for (const t of tagsToShow) {
        rows.push({
          type: "tag",
          groupName: group.groupName,
          colourSet: group.colourSet,
          tagName: t.name,
          colourIndex: t.colourIndex,
        });
        tagCount++;
      }
    }

    return rows;
  }, [groupedVocabulary, filtered, inputValue, exclude, maxSuggestions]);

  // ── Flat list of selectable tag indices (skipping headers) ──────────────

  const selectableIndices = useMemo(() => {
    return suggestRows
      .map((row, i) => (row.type === "tag" ? i : -1))
      .filter((i) => i >= 0);
  }, [suggestRows]);

  // Map suggestIndex to the tag name at that position.
  const selectedTagName = useMemo(() => {
    if (suggestIndex < 0 || suggestIndex >= suggestRows.length) return null;
    const row = suggestRows[suggestIndex];
    return row.type === "tag" ? row.tagName ?? null : null;
  }, [suggestIndex, suggestRows]);

  // Ghost text: suffix of best prefix match.
  const ghostText = useMemo(() => {
    const val = inputValue.trim().toLowerCase();
    if (!val) return "";

    // All tag names from suggest rows (for ghost lookup).
    const tagNames = suggestRows
      .filter((r) => r.type === "tag")
      .map((r) => r.tagName!);

    // If a suggestion is highlighted, use that.
    if (selectedTagName && selectedTagName.toLowerCase().startsWith(val)) {
      return selectedTagName.substring(inputValue.length);
    }
    // Otherwise find best prefix match from suggestions.
    const prefix = tagNames.find((n) => n.toLowerCase().startsWith(val));
    return prefix ? prefix.substring(inputValue.length) : "";
  }, [inputValue, selectedTagName, suggestRows]);

  // Auto-resize input box to fit typed text + ghost.
  useEffect(() => {
    if (!sizerRef.current || !boxRef.current) return;
    const fullText = inputValue + ghostText;
    sizerRef.current.textContent = fullText || placeholder;
    const w = Math.max(sizerRef.current.offsetWidth + 16, 48);
    boxRef.current.style.width = `${w}px`;
  }, [inputValue, ghostText, placeholder]);

  // Resolve the final value, accepting ghost text or highlighted suggestion.
  const resolveValue = useCallback((): string => {
    if (ghostText) {
      return inputValue + ghostText;
    }
    if (selectedTagName) {
      return selectedTagName;
    }
    return inputValue.trim();
  }, [inputValue, ghostText, selectedTagName]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const selCount = selectableIndices.length;

      if (e.key === "ArrowRight" && ghostText) {
        e.preventDefault();
        const accepted = inputValue + ghostText;
        setInputValue(accepted);
        setSuggestIndex(-1);
      } else if (e.key === "ArrowDown" && selCount > 0) {
        e.preventDefault();
        setSuggestIndex((prev) => {
          const curPos = selectableIndices.indexOf(prev);
          if (curPos < 0 || curPos >= selCount - 1) {
            // Wrap: go to first selectable, or -1 if at end.
            return curPos >= selCount - 1 ? -1 : selectableIndices[0];
          }
          return selectableIndices[curPos + 1];
        });
      } else if (e.key === "ArrowUp" && selCount > 0) {
        e.preventDefault();
        setSuggestIndex((prev) => {
          const curPos = selectableIndices.indexOf(prev);
          if (curPos <= 0) {
            // Wrap: go to last selectable, or -1 if at start.
            return curPos === 0 ? -1 : selectableIndices[selCount - 1];
          }
          return selectableIndices[curPos - 1];
        });
      } else if (e.key === "Enter") {
        e.preventDefault();
        e.stopPropagation();
        const val = resolveValue();
        if (val) {
          onCommit(val);
        } else {
          onCancel();
        }
      } else if (e.key === "Tab") {
        e.preventDefault();
        const val = resolveValue();
        if (val) {
          if (onCommitAndReopen) {
            onCommitAndReopen(val);
          } else {
            onCommit(val);
          }
        } else {
          onCancel();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    },
    [selectableIndices, ghostText, inputValue, resolveValue, onCommit, onCancel, onCommitAndReopen],
  );

  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (!mountedRef.current) return;
      const val = inputValue.trim();
      if (val) {
        onCommit(val);
      } else {
        onCancel();
      }
    }, 150);
  }, [inputValue, onCommit, onCancel]);

  const handleSuggestionClick = useCallback(
    (name: string) => (e: React.MouseEvent) => {
      e.preventDefault();
      onCommit(name);
    },
    [onCommit],
  );

  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    setSuggestIndex(-1);
  }, []);

  const classes = ["tag-input-wrap", className].filter(Boolean).join(" ");

  const hasSuggestions = suggestRows.some((r) => r.type === "tag");

  return (
    <span className={classes} data-testid={testId}>
      <span className="tag-input-box" ref={boxRef}>
        <input
          ref={inputRef}
          className="tag-input"
          type="text"
          placeholder={placeholder}
          value={inputValue}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          onBlur={handleBlur}
        />
        <span className="tag-ghost-layer">
          <span className="tag-ghost-spacer">{inputValue}</span>
          <span className="tag-ghost">{ghostText}</span>
        </span>
      </span>
      <span className="tag-sizer" ref={sizerRef} />
      {hasSuggestions && (
        <div className="tag-suggest" data-testid={testId ? `${testId}-dropdown` : undefined}>
          {suggestRows.map((row, idx) => {
            if (row.type === "header") {
              return (
                <div
                  key={`header-${row.groupName}`}
                  className="tag-suggest-header"
                  style={{ background: getGroupBg(row.colourSet) }}
                  aria-hidden="true"
                >
                  {row.groupName}
                </div>
              );
            }
            const tagName = row.tagName!;
            const isActive = idx === suggestIndex;
            const bgColour = row.colourSet
              ? getTagBg(row.colourSet, row.colourIndex ?? 0)
              : undefined;
            return (
              <div
                key={`${row.groupName}:${tagName}`}
                className={`tag-suggest-item${isActive ? " active" : ""}`}
                onMouseDown={handleSuggestionClick(tagName)}
                data-group={row.groupName || undefined}
              >
                <span
                  className="tag-suggest-pill"
                  style={bgColour ? { background: bgColour } : undefined}
                >
                  {tagName}
                </span>
                {hiddenTags?.has(tagName.toLowerCase()) && EyeClosedIcon}
              </div>
            );
          })}
        </div>
      )}
    </span>
  );
}
