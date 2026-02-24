import { useRef, useEffect, useCallback, useState } from "react";

interface EditableTextProps {
  value: string;
  originalValue?: string;
  isEditing?: boolean;
  committed?: boolean;
  onCommit: (newValue: string) => void;
  onCancel: () => void;
  trigger?: "external" | "click";
  as?: "span" | "p";
  className?: string;
  committedClassName?: string;
  "data-testid"?: string;
  "data-edit-key"?: string;
  /** When true (set synchronously by a parent), blur is suppressed. */
  suppressBlurRef?: React.RefObject<boolean>;
}

export function EditableText({
  value,
  originalValue,
  isEditing: isEditingProp,
  committed = false,
  onCommit,
  onCancel,
  trigger = "external",
  as: Tag = "span",
  className,
  committedClassName = "edited",
  "data-testid": testId,
  "data-edit-key": editKey,
  suppressBlurRef,
}: EditableTextProps) {
  const ref = useRef<HTMLElement>(null);
  const [internalEditing, setInternalEditing] = useState(false);
  const clickCoordsRef = useRef<{ x: number; y: number } | null>(null);

  const isEditing = trigger === "click" ? internalEditing : (isEditingProp ?? false);

  const baseline = originalValue ?? value;

  const finishEdit = useCallback(
    (newText: string) => {
      if (trigger === "click") setInternalEditing(false);
      if (newText !== baseline) {
        onCommit(newText);
      } else {
        onCancel();
      }
    },
    [trigger, baseline, onCommit, onCancel],
  );

  // When entering edit mode: focus, set text content, place caret.
  useEffect(() => {
    if (!isEditing || !ref.current) return;
    const el = ref.current;
    el.textContent = value;
    el.focus();

    // If we have click coordinates, place caret at the click position.
    // Otherwise (external trigger), select all text.
    const coords = clickCoordsRef.current;
    if (coords) {
      clickCoordsRef.current = null;
      try {
        let range: Range | null = null;
        if (document.caretRangeFromPoint) {
          range = document.caretRangeFromPoint(coords.x, coords.y);
        } else if ("caretPositionFromPoint" in document) {
          const pos = (document as unknown as { caretPositionFromPoint: (x: number, y: number) => { offsetNode: Node; offset: number } }).caretPositionFromPoint(coords.x, coords.y);
          if (pos) {
            range = document.createRange();
            range.setStart(pos.offsetNode, pos.offset);
            range.collapse(true);
          }
        }
        if (range) {
          const sel = window.getSelection();
          if (sel) {
            sel.removeAllRanges();
            sel.addRange(range);
          }
        }
      } catch {
        // Fallback: caret at end (focus already placed above)
      }
    } else {
      const range = document.createRange();
      range.selectNodeContents(el);
      const sel = window.getSelection();
      if (sel) {
        sel.removeAllRanges();
        sel.addRange(range);
      }
    }
    // Only run when isEditing flips — not when value changes during editing.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isEditing]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (!isEditing) return;
      if (e.key === "Escape") {
        e.preventDefault();
        if (trigger === "click") setInternalEditing(false);
        onCancel();
      } else if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        const newText = ref.current?.textContent?.trim() ?? "";
        finishEdit(newText);
      }
    },
    [isEditing, trigger, onCancel, finishEdit],
  );

  const handleBlur = useCallback(() => {
    if (!isEditing) return;
    if (suppressBlurRef?.current) return;
    const newText = ref.current?.textContent?.trim() ?? "";
    finishEdit(newText);
  }, [isEditing, finishEdit, suppressBlurRef]);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      if (trigger === "click" && !internalEditing) {
        clickCoordsRef.current = { x: e.clientX, y: e.clientY };
        setInternalEditing(true);
      }
    },
    [trigger, internalEditing],
  );

  const classes = [className, committed && committedClassName]
    .filter(Boolean)
    .join(" ") || undefined;

  const style = trigger === "click" && !isEditing ? { cursor: "text" as const } : undefined;

  return (
    <Tag
      ref={ref as React.Ref<never>}
      className={classes}
      style={style}
      contentEditable={isEditing || undefined}
      suppressContentEditableWarning={isEditing}
      onKeyDown={isEditing ? handleKeyDown : undefined}
      onBlur={isEditing ? handleBlur : undefined}
      onClick={trigger === "click" ? handleClick : undefined}
      data-testid={testId}
      data-edit-key={editKey}
    >
      {isEditing ? undefined : value}
    </Tag>
  );
}
