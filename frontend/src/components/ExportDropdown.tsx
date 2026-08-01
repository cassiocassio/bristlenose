/**
 * ExportDropdown — tab-contextual export action menu in the NavBar.
 *
 * On Quotes tab: Copy Quotes | Save as Spreadsheet | Export Report...
 * On other tabs: Export Report... only.
 *
 * Uses useDropdown for open/close and useMenuKeyboard for arrow-key
 * navigation per WAI-ARIA menu button pattern.
 */

import { useCallback, useMemo, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useDropdown } from "../hooks/useDropdown";
import { useMenuKeyboard } from "../hooks/useMenuKeyboard";
import { useProjectId } from "../hooks/useProjectId";
import { useFocus } from "../contexts/FocusContext";
import { useQuotesStore } from "../contexts/QuotesContext";
import { filterQuotes } from "../utils/filter";
import type { FilterState } from "../utils/filter";
import {
  copyQuotesToClipboard,
  saveQuotesSpreadsheet,
  extractVideoClips,
} from "../utils/exportActions";
import { isExportMode } from "../utils/exportData";

// ── Icon ──────────────────────────────────────────────────────────────────

function DownloadIcon() {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.4"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
    >
      <path d="M2 10v3.5h12V10" />
      <path d="M8 2v8" />
      <path d="M4.5 6.5L8 10l3.5-3.5" />
    </svg>
  );
}

// ── Helpers ────────────────────────────────────────────────────────────────

function isQuotesTab(pathname: string): boolean {
  return pathname === "/report/quotes" || pathname === "/report/quotes/";
}

// ── Props ─────────────────────────────────────────────────────────────────

interface ExportDropdownProps {
  onExportReport: () => void;
  onSendToMiro: () => void;
}

// ── Component ─────────────────────────────────────────────────────────────

export function ExportDropdown({ onExportReport, onSendToMiro }: ExportDropdownProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const projectId = useProjectId();
  const triggerRef = useRef<HTMLButtonElement | null>(null);

  const { open, setOpen, toggle, containerRef } = useDropdown();
  const { menuRef } = useMenuKeyboard({
    open,
    onClose: () => setOpen(false),
    triggerRef,
  });

  const onQuotes = isQuotesTab(location.pathname);

  // ── Quote count (only compute on Quotes tab) ─────────────────────────

  const store = useQuotesStore();
  const { selectedIds } = useFocus();

  const filterState: FilterState = useMemo(
    () => ({
      searchQuery: store.searchQuery,
      viewMode: store.viewMode,
      tagFilter: store.tagFilter,
      hidden: store.hidden,
      starred: store.starred,
      tags: store.tags,
    }),
    [store.searchQuery, store.viewMode, store.tagFilter, store.hidden, store.starred, store.tags],
  );

  const visibleQuotes = useMemo(
    () => (onQuotes ? filterQuotes(store.quotes, filterState) : []),
    [onQuotes, store.quotes, filterState],
  );

  // Three export scopes, mirroring the native Quotes menu. "All" = every quote
  // currently on screen (respects the toolbar filter, excludes hidden);
  // "Selected" = the live multi-selection; "Starred" = visible & starred. Each
  // export action (Copy · Spreadsheet · Clips) offers all three; a scope is
  // disabled when its set is empty.
  const allIds = useMemo(
    () => (onQuotes ? visibleQuotes.map((q) => q.dom_id) : []),
    [onQuotes, visibleQuotes],
  );
  const selectedScopeIds = useMemo(
    () => (onQuotes ? Array.from(selectedIds) : []),
    [onQuotes, selectedIds],
  );
  const starredScopeIds = useMemo(
    () =>
      onQuotes
        ? visibleQuotes.filter((q) => store.starred[q.dom_id]).map((q) => q.dom_id)
        : [],
    [onQuotes, visibleQuotes, store.starred],
  );

  // ── Handlers ──────────────────────────────────────────────────────────
  // Behaviour lives in utils/exportActions so the macOS native menu (via
  // AppLayout's bridge handlers) invokes the identical logic. Anonymise is
  // false here — on the web it rides the Export Report modal checkbox.

  const runScoped = useCallback(
    (action: "copy" | "spreadsheet" | "clips", ids: string[]) => {
      if (ids.length === 0) return;
      setOpen(false);
      if (action === "copy") void copyQuotesToClipboard(store, ids, t);
      else if (action === "spreadsheet") saveQuotesSpreadsheet(projectId, ids, t);
      else void extractVideoClips(ids, t);
    },
    [setOpen, store, projectId, t],
  );

  const handleExportReport = useCallback(() => {
    setOpen(false);
    onExportReport();
  }, [setOpen, onExportReport]);

  // Miro export — opens the multi-step modal (connect → configure → push),
  // mirroring Export Report. The panel lives in AppLayout; the macOS native
  // menu reaches it via the bridge's `sendToMiro` case.
  const handleSendToMiro = useCallback(() => {
    setOpen(false);
    onSendToMiro();
  }, [setOpen, onSendToMiro]);

  // Render one export action as a labelled group of three scope rows
  // (All / Selected / Starred), each disabled when its id set is empty.
  const renderScopeGroup = (
    action: "copy" | "spreadsheet" | "clips",
    heading: string,
    hint?: string,
  ) => {
    // `{{n}}`, not `{{count}}`, is deliberate: i18next reads a `count` option as a
    // plural selector, so these non-plural labels would resolve through `_one`/
    // `_other` stems that don't exist and fall back to the raw key. The native
    // twin (`desktop.menu.quotes.copyScope*`) does use `{{count}}` — Swift's I18n
    // only pluralises via an explicit `plural()` call, so there's no such trap.
    const scopes = [
      { key: "all", label: t("export.scope.all", { n: allIds.length }), ids: allIds },
      {
        key: "selected",
        label: t("export.scope.selected", { n: selectedScopeIds.length }),
        ids: selectedScopeIds,
      },
      {
        key: "starred",
        label: t("export.scope.starred", { n: starredScopeIds.length }),
        ids: starredScopeIds,
      },
    ];
    return (
      <>
        <li role="presentation" className="export-dropdown-group-label">
          {heading}
        </li>
        {scopes.map((s) => {
          const disabled = s.ids.length === 0;
          return (
            <li
              key={`${action}-${s.key}`}
              role="menuitem"
              tabIndex={-1}
              aria-disabled={disabled || undefined}
              className={`export-dropdown-item export-dropdown-scope${disabled ? " is-disabled" : ""}`}
              data-testid={`export-${action}-${s.key}`}
              onClick={disabled ? undefined : () => runScoped(action, s.ids)}
              onKeyDown={(e) => {
                if (!disabled && (e.key === "Enter" || e.key === " ")) {
                  e.preventDefault();
                  runScoped(action, s.ids);
                }
              }}
            >
              {s.label}
            </li>
          );
        })}
        {hint ? (
          <li role="none" className="export-dropdown-hint">
            {hint}
          </li>
        ) : null}
      </>
    );
  };

  // ── Render ────────────────────────────────────────────────────────────

  if (isExportMode()) return null;

  return (
    <div ref={containerRef} className="export-dropdown-wrapper" style={{ position: "relative" }}>
      <button
        ref={triggerRef}
        className="bn-tab bn-tab-icon"
        aria-label={t("buttons.export")}
        aria-haspopup="menu"
        aria-expanded={open}
        title={t("buttons.export")}
        onClick={toggle}
      >
        <DownloadIcon />
      </button>

      {open && (
        <ul
          ref={menuRef}
          role="menu"
          className="export-dropdown-menu"
          data-testid="export-dropdown-menu"
        >
          {onQuotes && (
            <>
              {renderScopeGroup("copy", t("export.copyQuotes"), t("export.pasteHint"))}
              <li role="separator" className="export-dropdown-separator" />
              {renderScopeGroup("spreadsheet", t("export.saveAsSpreadsheet"))}
              <li role="separator" className="export-dropdown-separator" />
              {renderScopeGroup("clips", t("export.extractClips"))}
              <li role="separator" className="export-dropdown-separator" />
            </>
          )}
          <li
            role="menuitem"
            tabIndex={-1}
            className="export-dropdown-item"
            onClick={handleExportReport}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleExportReport();
              }
            }}
          >
            {t("export.exportReport")}
          </li>
          <li role="separator" className="export-dropdown-separator" />
          <li
            role="menuitem"
            tabIndex={-1}
            className="export-dropdown-item"
            onClick={handleSendToMiro}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                handleSendToMiro();
              }
            }}
          >
            {t("miro.menuLabel")}
          </li>
        </ul>
      )}
    </div>
  );
}
