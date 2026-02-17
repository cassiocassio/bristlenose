import { useState, useRef, useMemo, useEffect, useCallback } from "react";

interface TagInputProps {
  /** All known tag names for auto-suggest. */
  vocabulary: string[];
  /** Tags to exclude from suggestions (already on this target). */
  exclude?: string[];
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
  exclude,
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

  // Filter vocabulary: case-insensitive contains match, not exact match, not excluded.
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

  // Ghost text: suffix of best prefix match.
  const ghostText = useMemo(() => {
    const val = inputValue.trim().toLowerCase();
    if (!val) return "";
    // If a suggestion is highlighted and starts with the typed text, show its suffix.
    if (suggestIndex >= 0 && suggestIndex < filtered.length) {
      const sel = filtered[suggestIndex];
      if (sel.toLowerCase().startsWith(val)) {
        return sel.substring(inputValue.length);
      }
      return "";
    }
    // Otherwise find best prefix match.
    const prefix = filtered.find((n) => n.toLowerCase().startsWith(val));
    return prefix ? prefix.substring(inputValue.length) : "";
  }, [inputValue, suggestIndex, filtered]);

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
    if (suggestIndex >= 0 && suggestIndex < filtered.length) {
      return filtered[suggestIndex];
    }
    return inputValue.trim();
  }, [inputValue, ghostText, suggestIndex, filtered]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      const count = filtered.length;

      if (e.key === "ArrowRight" && ghostText) {
        e.preventDefault();
        const accepted = inputValue + ghostText;
        setInputValue(accepted);
        setSuggestIndex(-1);
      } else if (e.key === "ArrowDown" && count > 0) {
        e.preventDefault();
        setSuggestIndex((prev) => (prev >= count - 1 ? -1 : prev + 1));
      } else if (e.key === "ArrowUp" && count > 0) {
        e.preventDefault();
        setSuggestIndex((prev) => (prev <= -1 ? count - 1 : prev - 1));
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
    [filtered, ghostText, inputValue, resolveValue, onCommit, onCancel, onCommitAndReopen],
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
      {filtered.length > 0 && (
        <div className="tag-suggest">
          {filtered.map((name, idx) => (
            <div
              key={name}
              className={`tag-suggest-item${idx === suggestIndex ? " active" : ""}`}
              onMouseDown={handleSuggestionClick(name)}
            >
              {name}
            </div>
          ))}
        </div>
      )}
    </span>
  );
}
