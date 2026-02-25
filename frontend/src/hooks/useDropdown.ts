/**
 * useDropdown — headless hook for dropdown open/close behaviour.
 *
 * Handles click-outside dismiss and Escape key close.
 * Returns open state and a container ref to attach to the dropdown wrapper.
 *
 * Consumers own the rendering (trigger button and menu content).
 * The hook only manages the behavioural layer.
 *
 * Supports both controlled mode (isOpen + onToggle props) and
 * uncontrolled mode (internal state). Toolbar uses controlled mode
 * for mutual exclusion of dropdowns.
 */

import { useCallback, useEffect, useRef, useState } from "react";

export interface UseDropdownOptions {
  /** Controlled open state. When provided, the hook does not manage its own state. */
  isOpen?: boolean;
  /** Called when open state should change (controlled mode). */
  onToggle?: (open: boolean) => void;
}

export interface UseDropdownReturn {
  open: boolean;
  setOpen: (v: boolean) => void;
  toggle: () => void;
  containerRef: React.RefObject<HTMLDivElement | null>;
}

export function useDropdown(options: UseDropdownOptions = {}): UseDropdownReturn {
  const controlled = options.isOpen !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);

  const open = controlled ? options.isOpen! : internalOpen;

  const setOpen = useCallback(
    (v: boolean) => {
      if (controlled) {
        options.onToggle?.(v);
      } else {
        setInternalOpen(v);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [controlled, options.onToggle],
  );

  const toggle = useCallback(() => setOpen(!open), [setOpen, open]);

  const containerRef = useRef<HTMLDivElement | null>(null);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    function onClickOutside(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", onClickOutside);
    return () => document.removeEventListener("mousedown", onClickOutside);
  }, [open, setOpen]);

  // Close on Escape
  useEffect(() => {
    if (!open) return;
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.stopPropagation();
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, setOpen]);

  return { open, setOpen, toggle, containerRef };
}
