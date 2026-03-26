/**
 * useMenuKeyboard — arrow-key navigation and focus management for role="menu".
 *
 * Complements useDropdown (which handles open/close) by adding the keyboard
 * behaviour required by WAI-ARIA Authoring Practices for menu buttons:
 * - ArrowDown/ArrowUp to navigate menuitems
 * - Home/End to jump to first/last
 * - Enter/Space to activate the focused item
 * - Focus moves to first item on open, returns to trigger on close
 *
 * Menu items are identified by `role="menuitem"` within the menu container.
 * Non-menuitem elements (hints, separators) are skipped during navigation.
 */

import { useEffect, useRef } from "react";

export interface UseMenuKeyboardOptions {
  /** Whether the menu is currently open. */
  open: boolean;
  /** Called to close the menu. */
  onClose: () => void;
  /** Ref to the trigger button (for focus restore on close). */
  triggerRef: React.RefObject<HTMLElement | null>;
}

export interface UseMenuKeyboardReturn {
  /** Attach to the `<ul role="menu">` element. */
  menuRef: React.RefObject<HTMLUListElement | null>;
}

export function useMenuKeyboard(options: UseMenuKeyboardOptions): UseMenuKeyboardReturn {
  const { open, onClose, triggerRef } = options;
  const menuRef = useRef<HTMLUListElement | null>(null);

  // Focus first menuitem when menu opens
  useEffect(() => {
    if (!open) return;
    requestAnimationFrame(() => {
      const items = getMenuItems(menuRef.current);
      if (items.length > 0) {
        items[0].focus();
      }
    });
  }, [open]);

  // Restore focus to trigger on close
  const prevOpen = useRef(open);
  useEffect(() => {
    if (prevOpen.current && !open) {
      triggerRef.current?.focus();
    }
    prevOpen.current = open;
  }, [open, triggerRef]);

  // Keyboard handler
  useEffect(() => {
    if (!open) return;
    const menu = menuRef.current;
    if (!menu) return;

    function onKeyDown(e: KeyboardEvent) {
      const items = getMenuItems(menuRef.current);
      if (items.length === 0) return;

      const active = document.activeElement as HTMLElement;
      const currentIndex = items.indexOf(active);

      switch (e.key) {
        case "ArrowDown": {
          e.preventDefault();
          const next = currentIndex < items.length - 1 ? currentIndex + 1 : 0;
          items[next].focus();
          break;
        }
        case "ArrowUp": {
          e.preventDefault();
          const prev = currentIndex > 0 ? currentIndex - 1 : items.length - 1;
          items[prev].focus();
          break;
        }
        case "Home": {
          e.preventDefault();
          items[0].focus();
          break;
        }
        case "End": {
          e.preventDefault();
          items[items.length - 1].focus();
          break;
        }
        case "Enter":
        case " ": {
          e.preventDefault();
          if (currentIndex >= 0) {
            active.click();
          }
          break;
        }
        case "Tab": {
          // Trap focus within menu — close instead of tabbing out
          e.preventDefault();
          onClose();
          break;
        }
      }
    }

    menu.addEventListener("keydown", onKeyDown);
    return () => menu.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  return { menuRef };
}

/** Get all focusable menuitem elements within a menu container. */
function getMenuItems(menu: HTMLElement | null): HTMLElement[] {
  if (!menu) return [];
  return Array.from(menu.querySelectorAll<HTMLElement>('[role="menuitem"]'));
}
