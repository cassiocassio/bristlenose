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
}: EditableTextProps) {
  const ref = useRef<HTMLElement>(null);
  const [internalEditing, setInternalEditing] = useState(false);

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

  // When entering edit mode: focus, set text content, select all.
  useEffect(() => {
    if (!isEditing || !ref.current) return;
    const el = ref.current;
    el.textContent = value;
    el.focus();
    const range = document.createRange();
    range.selectNodeContents(el);
    const sel = window.getSelection();
    if (sel) {
      sel.removeAllRanges();
      sel.addRange(range);
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
    const newText = ref.current?.textContent?.trim() ?? "";
    finishEdit(newText);
  }, [isEditing, finishEdit]);

  const handleClick = useCallback(() => {
    if (trigger === "click" && !internalEditing) {
      setInternalEditing(true);
    }
  }, [trigger, internalEditing]);

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
