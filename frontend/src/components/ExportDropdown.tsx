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
import { authHeaders } from "../utils/api";
import { toast } from "../utils/toast";
import { announce } from "../utils/announce";
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
}

// ── Component ─────────────────────────────────────────────────────────────

export function ExportDropdown({ onExportReport }: ExportDropdownProps) {
  const { t, i18n: i18nInstance } = useTranslation();
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

  // ── Build column headers from locale ──────────────────────────────────

  const colHeaders = useMemo(() => {
    const keys = [
      "export.colQuote",
      "export.colParticipantCode",
      "export.colParticipantName",
      "export.colSection",
      "export.colTheme",
      "export.colSentiment",
      "export.colTags",
      "export.colStarred",
      "export.colTimecode",
      "export.colSession",
      "export.colSourceFile",
    ];
    return keys.map((k) => t(k)).join(",");
  }, [t, i18nInstance.language]);

  // ── Handlers ──────────────────────────────────────────────────────────

  const handleCopyQuotes = useCallback(() => {
    setOpen(false);
    if (quoteCount === 0) {
      toast(t("export.noQuotesMatch"));
      return;
    }
    const idsParam = exportIds.join(",");
    const url = `/api/projects/${projectId}/export/quotes.csv?quote_ids=${encodeURIComponent(idsParam)}&col_headers=${encodeURIComponent(colHeaders)}`;

    // ClipboardItem with a Promise<Blob> value reserves the clipboard write
    // synchronously (preserving the user gesture) while the fetch resolves
    // asynchronously.  The write() call MUST be in the synchronous call stack
    // — never inside .then() — or Safari rejects with NotAllowedError.
    const blobPromise = globalThis
      .fetch(url, { headers: authHeaders() })
      .then((resp) => {
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return resp.text();
      })
      .then((text) => new Blob([text], { type: "text/plain" }));

    let copyPromise: Promise<void>;
    if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
      // Synchronous write() call — Promise<Blob> resolves inside the browser
      const item = new ClipboardItem({ "text/plain": blobPromise });
      copyPromise = navigator.clipboard.write([item]);
    } else {
      // Fallback for environments without ClipboardItem (jsdom, old browsers)
      copyPromise = blobPromise
        .then((blob) => blob.text())
        .then((text) => navigator.clipboard.writeText(text));
    }

    copyPromise
      .then(() => {
        const msg = t("export.quotesCopied", { count: quoteCount });
        toast(msg);
        announce(msg);
      })
      .catch((err) => {
        console.error("[ExportDropdown] Copy failed:", err);
        toast(t("export.exportFailed"));
      });
  }, [setOpen, quoteCount, exportIds, projectId, colHeaders, t]);

  const handleSaveSpreadsheet = useCallback(async () => {
    setOpen(false);
    if (quoteCount === 0) {
      toast(t("export.noQuotesMatch"));
      return;
    }
    const idsParam = exportIds.join(",");
    try {
      const resp = await globalThis.fetch(
        `/api/projects/${projectId}/export/quotes.xlsx?quote_ids=${encodeURIComponent(idsParam)}&col_headers=${encodeURIComponent(colHeaders)}`,
        { headers: authHeaders() },
      );
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const blob = await resp.blob();
      const cd = resp.headers.get("content-disposition") ?? "";
      const match = cd.match(/filename="(.+)"/);
      const filename = match?.[1] ?? "quotes.xlsx";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("[ExportDropdown] Spreadsheet download failed:", err);
      toast(t("export.exportFailed"));
    }
  }, [setOpen, quoteCount, exportIds, projectId, colHeaders, t]);

  const handleExportReport = useCallback(() => {
    setOpen(false);
    onExportReport();
  }, [setOpen, onExportReport]);

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
        </ul>
      )}
    </div>
  );
}
