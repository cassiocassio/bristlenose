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

  const exportIds = useMemo(() => {
    if (!onQuotes) return [];
    if (selectedIds.size > 0) return Array.from(selectedIds);
    return visibleQuotes.map((q) => q.dom_id);
  }, [onQuotes, selectedIds, visibleQuotes]);

  const quoteCount = exportIds.length;

  // ── Handlers ──────────────────────────────────────────────────────────
  // Behaviour lives in utils/exportActions so the macOS native menu (via
  // AppLayout's bridge handlers) invokes the identical logic. Anonymise is
  // false here — on the web it rides the Export Report modal checkbox.

  const handleCopyQuotes = useCallback(() => {
    setOpen(false);
    void copyQuotesToClipboard(store, exportIds, t);
  }, [setOpen, store, exportIds, t]);

  const handleSaveSpreadsheet = useCallback(() => {
    setOpen(false);
    saveQuotesSpreadsheet(projectId, exportIds, t);
  }, [setOpen, projectId, exportIds, t]);

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

  const handleExtractClips = useCallback(() => {
    setOpen(false);
    void extractVideoClips(t);
  }, [setOpen, t]);

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
              <li
                role="menuitem"
                tabIndex={-1}
                className="export-dropdown-item"
                onClick={handleCopyQuotes}
              >
                {t("export.copyQuotesCount", { count: quoteCount })}
              </li>
              <li role="none" className="export-dropdown-hint">
                {t("export.pasteHint")}
              </li>
              <li role="separator" className="export-dropdown-separator" />
              <li
                role="menuitem"
                tabIndex={-1}
                className="export-dropdown-item"
                onClick={handleSaveSpreadsheet}
              >
                {t("export.saveAsSpreadsheet")}
              </li>
              <li role="separator" className="export-dropdown-separator" />
              <li
                role="menuitem"
                tabIndex={-1}
                className="export-dropdown-item"
                onClick={handleExtractClips}
              >
                {t("export.extractClips")}
              </li>
              <li role="separator" className="export-dropdown-separator" />
            </>
          )}
          <li
            role="menuitem"
            tabIndex={-1}
            className="export-dropdown-item"
            onClick={handleExportReport}
          >
            {t("export.exportReport")}
          </li>
          <li role="separator" className="export-dropdown-separator" />
          <li
            role="menuitem"
            tabIndex={-1}
            className="export-dropdown-item"
            onClick={handleSendToMiro}
          >
            {t("miro.menuLabel")}
          </li>
        </ul>
      )}
    </div>
  );
}
