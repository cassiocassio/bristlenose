/**
 * ModalNav — reusable sidebar-nav modal shell.
 *
 * Generic two-column layout: sidebar navigation + content pane.
 * Supports disclosure sub-items (collapsible groups) and an optional
 * search slot above the nav list.  Responsive: collapses to a
 * dropdown selector at narrow viewports (≤500px via CSS).
 *
 * Used by SettingsModal; designed to be reusable for About/Help later.
 *
 * @module ModalNav
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

// ── Types ─────────────────────────────────────────────────────────────────

export interface NavSubItem {
  id: string;
  label: string;
}

export interface NavItem {
  id: string;
  label: string;
  /** If present, this item is a disclosure group with sub-items. */
  children?: NavSubItem[];
}

export interface ModalNavProps {
  open: boolean;
  onClose: () => void;
  /** Modal title (rendered as h2). */
  title: string;
  /** Navigation sections. */
  items: NavItem[];
  /** Currently active section ID. */
  activeId: string;
  /** Called when user selects a nav item. */
  onSelect: (id: string) => void;
  /** Content to render in the main pane. */
  children: React.ReactNode;
  /** Optional slot above the nav list (e.g. search input). */
  searchSlot?: React.ReactNode;
  /** Extra CSS class on the .bn-modal element. */
  className?: string;
  /** data-testid for the overlay. */
  testId?: string;
}

// ── Component ─────────────────────────────────────────────────────────────

export function ModalNav({
  open,
  onClose,
  title,
  items,
  activeId,
  onSelect,
  children,
  searchSlot,
  className,
  testId,
}: ModalNavProps) {
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    // Auto-expand any group whose child is active on mount.
    const expanded = new Set<string>();
    for (const item of items) {
      if (item.children?.some((c) => c.id === activeId)) {
        expanded.add(item.id);
      }
    }
    return expanded;
  });

  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const triggerRef = useRef<Element | null>(null);
  const contentHeadingRef = useRef<HTMLHeadingElement>(null);

  // Track the element that had focus when the modal opened.
  useEffect(() => {
    if (open) {
      triggerRef.current = document.activeElement;
      // Focus the close button on open.
      requestAnimationFrame(() => closeButtonRef.current?.focus());
    } else if (triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
      triggerRef.current = null;
    }
  }, [open]);

  // Close on Escape.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", handler, true);
    return () => document.removeEventListener("keydown", handler, true);
  }, [open, onClose]);

  // Focus trap.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key !== "Tab") return;
      const modal = document.querySelector(`[data-testid="${testId ?? "modal-nav"}"] .bn-modal`);
      if (!modal) return;
      const focusable = modal.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
      );
      if (focusable.length === 0) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (e.shiftKey && document.activeElement === first) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && document.activeElement === last) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [open, testId]);

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose],
  );

  const toggleGroup = useCallback((id: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const handleNavSelect = useCallback(
    (id: string) => {
      onSelect(id);
      // Move focus to content heading for screen readers.
      requestAnimationFrame(() => contentHeadingRef.current?.focus());
    },
    [onSelect],
  );

  // Auto-expand group when a child becomes active.
  useEffect(() => {
    for (const item of items) {
      if (item.children?.some((c) => c.id === activeId)) {
        setExpandedGroups((prev) => {
          if (prev.has(item.id)) return prev;
          const next = new Set(prev);
          next.add(item.id);
          return next;
        });
      }
    }
  }, [activeId, items]);

  // Determine the label of the active section (for dropdown + heading).
  const activeLabel =
    items.flatMap((item) => [item, ...(item.children ?? [])]).find((i) => i.id === activeId)
      ?.label ?? "";

  return createPortal(
    <div
      className={`bn-overlay settings-overlay${open ? " visible" : ""}`}
      onClick={handleOverlayClick}
      aria-hidden={!open}
      data-testid={testId ?? "modal-nav"}
    >
      <div
        className={`bn-modal ${className ?? ""}`.trim()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-nav-title"
      >
        <button
          ref={closeButtonRef}
          className="bn-modal-close"
          onClick={onClose}
          aria-label="Close"
        >
          &times;
        </button>
        <h2 id="modal-nav-title" className="modal-nav-title">
          {title}
        </h2>

        <div className="modal-nav">
          {/* ── Sidebar (desktop) ── */}
          <nav className="modal-nav-sidebar" aria-label={`${title} sections`}>
            {searchSlot && <div className="modal-nav-search">{searchSlot}</div>}
            <ul className="modal-nav-list" role="navigation">
              {items.map((item) =>
                item.children ? (
                  <li key={item.id}>
                    <button
                      className="modal-nav-item modal-nav-disclosure"
                      aria-expanded={expandedGroups.has(item.id)}
                      aria-controls={`modal-nav-sub-${item.id}`}
                      onClick={() => toggleGroup(item.id)}
                    >
                      <span
                        className={`modal-nav-arrow${expandedGroups.has(item.id) ? " expanded" : ""}`}
                        aria-hidden="true"
                      >
                        &#9654;
                      </span>
                      {item.label}
                    </button>
                    {expandedGroups.has(item.id) && (
                      <ul id={`modal-nav-sub-${item.id}`} className="modal-nav-sub-list">
                        {item.children.map((child) => (
                          <li key={child.id}>
                            <button
                              className={`modal-nav-item modal-nav-sub${activeId === child.id ? " active" : ""}`}
                              aria-current={activeId === child.id ? "page" : undefined}
                              onClick={() => handleNavSelect(child.id)}
                            >
                              {child.label}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ) : (
                  <li key={item.id}>
                    <button
                      className={`modal-nav-item${activeId === item.id ? " active" : ""}`}
                      aria-current={activeId === item.id ? "page" : undefined}
                      onClick={() => handleNavSelect(item.id)}
                    >
                      {item.label}
                    </button>
                  </li>
                ),
              )}
            </ul>
          </nav>

          {/* ── Dropdown (narrow viewports) ── */}
          <div className="modal-nav-dropdown">
            <select
              value={activeId}
              onChange={(e) => handleNavSelect(e.target.value)}
              aria-label={`${title} section`}
              className="bn-locale-select"
            >
              {items.map((item) =>
                item.children ? (
                  <optgroup key={item.id} label={item.label}>
                    {item.children.map((child) => (
                      <option key={child.id} value={child.id}>
                        {child.label}
                      </option>
                    ))}
                  </optgroup>
                ) : (
                  <option key={item.id} value={item.id}>
                    {item.label}
                  </option>
                ),
              )}
            </select>
          </div>

          {/* ── Content pane ── */}
          <div className="modal-nav-content">
            <h3
              ref={contentHeadingRef}
              className="modal-nav-content-heading"
              tabIndex={-1}
            >
              {activeLabel}
            </h3>
            {children}
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
