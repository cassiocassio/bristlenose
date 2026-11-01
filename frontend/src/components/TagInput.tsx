import { useState, useRef, useMemo, useEffect, useCallback } from "react";
import { getTagBg, getGroupBg } from "../utils/colours";
import { Icon } from "./Icon";

/** Small closed-eye icon shown next to autocomplete suggestions whose codebook group is hidden. */
const EyeClosedIcon = (
  <Icon name="hide" px={12} decorative className="tag-suggest-hidden-icon" />
);

/** A codebook group with its tags, used for structured autocomplete. */
export interface TagVocabularyGroup {
  groupName: string;
  colourSet: string;
  /** The codebook the group came from; null is the researcher's own. Absent in older callers. */
  frameworkId?: string | null;
  /** `id` is the tag's row: a pick commits it, because two tags can share a name (N146). */
  tags: { name: string; colourIndex: number; id?: number }[];
}

/** The tag a researcher chose from the list, as the row it is. */
export interface TagPick {
  id: number;
  groupName: string;
  colourSet: string;
  colourIndex: number;
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
  /** The tag's row (only for type=tag, when the vocabulary carries it). */
  tagId?: number;
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
  onCommit: (tagName: string, pick?: TagPick) => void;
  /** Called when user cancels (Escape, blur with empty). */
  onCancel: () => void;
  /** Called on Tab commit — consumer handles unmount→remount for rapid entry. */
  onCommitAndReopen?: (tagName: string, pick?: TagPick) => void;
  /** Placeholder text. */
  placeholder?: string;
  /** Maximum suggestions shown in dropdown. */
  maxSuggestions?: number;
  className?: string;
  "data-testid"?: string;
}

/** Call a commit with the pick only when there is one, so a caller that ignores picks sees the
 *  one-argument call it always did. */
function commitWith(
  commit: (name: string, pick?: TagPick) => void,
  name: string,
  pick: TagPick | undefined,
): void {
  if (pick) commit(name, pick);
  else commit(name);
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
  maxSuggestions = 12,
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

    // A name two tags share still lists both when it is typed whole, so the researcher can
    // choose between them; a name only one tag has is the typed text itself and is not repeated.
    const sharedNames = new Map<string, number>();
    for (const group of groupedVocabulary) {
      for (const t of group.tags) {
        const lower = t.name.toLowerCase();
        sharedNames.set(lower, (sharedNames.get(lower) ?? 0) + 1);
      }
    }

    const rows: SuggestRow[] = [];
    let tagCount = 0;

    for (const group of groupedVocabulary) {
      const groupNameMatches = group.groupName.toLowerCase().includes(val);

      const matchingTags = group.tags.filter((t) => {
        const lower = t.name.toLowerCase();
        // Show tag if: tag name matches OR group name matches (show all tags in group).
        const matches = lower.includes(val) || groupNameMatches;
        const isTypedWhole = lower === val && (sharedNames.get(lower) ?? 0) > 1;
        return matches && (lower !== val || isTypedWhole) && !excSet.has(lower);
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
          tagId: t.id,
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

  // Map suggestIndex to the tag at that position.
  const selectedRow = useMemo(() => {
    if (suggestIndex < 0 || suggestIndex >= suggestRows.length) return null;
    const row = suggestRows[suggestIndex];
    return row.type === "tag" ? row : null;
  }, [suggestIndex, suggestRows]);
  const selectedTagName = selectedRow?.tagName ?? null;

  // True when what is typed is, already, the full name of an existing tag.
  // Suggestions drop that exact row (below), so without this the ghost would
  // complete to a longer sibling ("trust" -> "trustworthiness") and Return
  // would apply a tag the researcher did not type, while blur applies what
  // they typed. An arrow-selected suggestion still wins (see resolveValue).
  const typedIsExistingTag = useMemo(() => {
    const val = inputValue.trim().toLowerCase();
    if (!val) return false;
    if (vocabulary.some((n) => n.toLowerCase() === val)) return true;
    return (groupedVocabulary ?? []).some((g) =>
      g.tags.some((t) => t.name.toLowerCase() === val),
    );
  }, [inputValue, vocabulary, groupedVocabulary]);

  // Ghost text: suffix of best prefix match.
  const ghostText = useMemo(() => {
    // Match and slice on the trimmed text: "tru " must not splice a stray
    // character into the completion (the commit uses the trimmed text too).
    const typed = inputValue.trim();
    const val = typed.toLowerCase();
    if (!val) return "";

    // All tag names from suggest rows (for ghost lookup).
    const tagNames = suggestRows
      .filter((r) => r.type === "tag")
      .map((r) => r.tagName!);

    // If a suggestion is highlighted, use that.
    if (selectedTagName && selectedTagName.toLowerCase().startsWith(val)) {
      return selectedTagName.substring(typed.length);
    }
    // A complete existing name is not a prefix to be completed.
    if (typedIsExistingTag) return "";
    // Otherwise find best prefix match from suggestions.
    const prefix = tagNames.find((n) => n.toLowerCase().startsWith(val));
    return prefix ? prefix.substring(typed.length) : "";
  }, [inputValue, selectedTagName, suggestRows, typedIsExistingTag]);

  // Auto-resize input box to fit typed text + ghost.
  useEffect(() => {
    if (!sizerRef.current || !boxRef.current) return;
    const fullText = inputValue + ghostText;
    sizerRef.current.textContent = fullText || placeholder;
    const w = Math.max(sizerRef.current.offsetWidth + 16, 48);
    boxRef.current.style.width = `${w}px`;
  }, [inputValue, ghostText, placeholder]);

  // Resolve the final value: highlighted suggestion wins over ghost text.
  // The user explicitly arrowed to a suggestion — that's their choice,
  // even if ghost text shows a different prefix-match completion.
  const resolveValue = useCallback((): string => {
    if (selectedTagName) {
      return selectedTagName;
    }
    if (ghostText) {
      return inputValue.trim() + ghostText;
    }
    return inputValue.trim();
  }, [inputValue, ghostText, selectedTagName]);

  // The tag a committed value means. An arrowed row is that row's tag. A typed (or ghost-completed)
  // whole name is the researcher's own tag of that name if they have one: the vocabulary lists their
  // groups first, and the machine-authored sentiment tags are never the answer to a typed name
  // (the server resolves it the same way). Nothing found: no pick, and the server decides.
  const pickFor = useCallback(
    (name: string): TagPick | undefined => {
      if (selectedRow && selectedRow.tagName === name && selectedRow.tagId != null) {
        return {
          id: selectedRow.tagId,
          groupName: selectedRow.groupName,
          colourSet: selectedRow.colourSet,
          colourIndex: selectedRow.colourIndex ?? 0,
        };
      }
      const lower = name.toLowerCase();
      for (const g of groupedVocabulary ?? []) {
        if (g.frameworkId === "sentiment") continue;
        const t = g.tags.find((x) => x.name.toLowerCase() === lower && x.id != null);
        if (t) {
          return { id: t.id!, groupName: g.groupName, colourSet: g.colourSet, colourIndex: t.colourIndex };
        }
      }
      return undefined;
    },
    [selectedRow, groupedVocabulary],
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const selCount = selectableIndices.length;

      if (e.key === "ArrowRight" && ghostText) {
        e.preventDefault();
        const accepted = inputValue.trim() + ghostText;
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
          commitWith(onCommit, val, pickFor(val));
        } else {
          onCancel();
        }
      } else if (e.key === "Tab") {
        e.preventDefault();
        const val = resolveValue();
        if (val) {
          if (onCommitAndReopen) {
            commitWith(onCommitAndReopen, val, pickFor(val));
          } else {
            commitWith(onCommit, val, pickFor(val));
          }
        } else {
          onCancel();
        }
      } else if (e.key === "Escape") {
        e.preventDefault();
        onCancel();
      }
    },
    [selectableIndices, ghostText, inputValue, resolveValue, pickFor, onCommit, onCancel, onCommitAndReopen],
  );

  const handleBlur = useCallback(() => {
    setTimeout(() => {
      if (!mountedRef.current) return;
      const val = inputValue.trim();
      if (val) {
        commitWith(onCommit, val, pickFor(val));
      } else {
        onCancel();
      }
    }, 150);
  }, [inputValue, pickFor, onCommit, onCancel]);

  const handleSuggestionClick = useCallback(
    (name: string, pick?: TagPick) => (e: React.MouseEvent) => {
      e.preventDefault();
      commitWith(onCommit, name, pick);
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
              // Pointer-select path for an autocomplete suggestion; keyboard selection is handled on the input via handleKeyDown.
              // eslint-disable-next-line jsx-a11y/no-static-element-interactions
              <div
                key={`${row.groupName}:${tagName}`}
                className={`tag-suggest-item${isActive ? " active" : ""}`}
                onMouseDown={handleSuggestionClick(
                  tagName,
                  row.tagId != null
                    ? {
                        id: row.tagId,
                        groupName: row.groupName,
                        colourSet: row.colourSet,
                        colourIndex: row.colourIndex ?? 0,
                      }
                    : undefined,
                )}
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
