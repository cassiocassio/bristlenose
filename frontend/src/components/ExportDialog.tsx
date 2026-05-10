/**
 * ExportDialog — modal for exporting a self-contained HTML report.
 *
 * Triggered from the NavBar export button.  Options: anonymise checkbox.
 * Calls the server export endpoint and triggers a file download.
 *
 * @module ExportDialog
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useInert } from "../hooks/useInert";
import { useProjectId } from "../hooks/useProjectId";
import { isExportMode } from "../utils/exportData";

interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  /** Pre-select the anonymise checkbox when opening (e.g. from Export Anonymised menu). */
  initialAnonymise?: boolean;
}

export function ExportDialog({ open, onClose, initialAnonymise = false }: ExportDialogProps) {
  const { t } = useTranslation();
  useInert(open);
  const projectId = useProjectId();
  const [anonymise, setAnonymise] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const triggerRef = useRef<Element | null>(null);

  // Reset state and track trigger element when opening.
  useEffect(() => {
    if (open) {
      setAnonymise(initialAnonymise);
      setError(null);
      triggerRef.current = document.activeElement;
    } else if (triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
      triggerRef.current = null;
    }
  }, [open]);

  const handleOverlayClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) onClose();
    },
    [onClose],
  );

  // Close on Escape
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

  const handleExport = useCallback(() => {
    // Direct anchor navigation — no fetch, no blob.  The auth cookie set on
    // the SPA HTML response carries the bearer token; the server replies
    // with `Content-Disposition: attachment` and (in the desktop app)
    // WKDownload routes the bytes through NSSavePanel.  In the browser the
    // native download UI takes over.
    setError(null);
    const qs = anonymise ? "?anonymise=true" : "";
    const url = `/api/projects/${projectId}/export${qs}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "";  // hint download intent; server's Content-Disposition wins
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    onClose();
  }, [anonymise, onClose, projectId]);

  if (isExportMode()) return null;

  return createPortal(
    <div
      className={`bn-overlay${open ? " visible" : ""}`}
      onClick={handleOverlayClick}
      aria-hidden={!open}
      data-testid="bn-export-overlay"
    >
      <div className="bn-modal" data-testid="bn-export-modal" style={{ maxWidth: 420 }}>
        <h2>{t("export.heading")}</h2>
        <p className="bn-modal-subtitle">
          {t("export.subtitle")}
        </p>
        <label className="bn-export-checkbox">
          <input
            type="checkbox"
            checked={anonymise}
            onChange={(e) => setAnonymise(e.target.checked)}
                      />
          <span>
            {t("export.anonymise")}
            <small className="bn-export-hint">
              {t("export.anonymiseHint")}
            </small>
          </span>
        </label>
        {error && (
          <p className="bn-export-error" role="alert">
            {error}
          </p>
        )}
        <div className="bn-modal-actions">
          <button
            className="bn-btn bn-btn-secondary"
            onClick={onClose}
          >
            {t("buttons.cancel")}
          </button>
          <button
            className="bn-btn bn-btn-primary"
            onClick={handleExport}
          >
            {t("buttons.export")}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
