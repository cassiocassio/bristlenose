/**
 * ExportDialog — modal for exporting a self-contained HTML report.
 *
 * Triggered from the NavBar export button.  Options: anonymise checkbox.
 * Calls the server export endpoint and triggers a file download.
 *
 * @module ExportDialog
 */

import { useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { isExportMode } from "../utils/exportData";

interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
}

export function ExportDialog({ open, onClose }: ExportDialogProps) {
  const [anonymise, setAnonymise] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

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

  const handleExport = useCallback(async () => {
    setExporting(true);
    setError(null);
    try {
      const qs = anonymise ? "?anonymise=true" : "";
      const resp = await globalThis.fetch(
        `/api/projects/1/export${qs}`,
      );
      if (!resp.ok) {
        throw new Error(`Export failed (${resp.status})`);
      }
      // Extract filename from Content-Disposition header
      const cd = resp.headers.get("content-disposition") || "";
      const filenameMatch = cd.match(/filename="([^"]+)"/);
      const filename = filenameMatch ? filenameMatch[1] : "bristlenose-report.html";

      // Create blob and trigger download
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setExporting(false);
    }
  }, [anonymise, onClose]);

  if (!open || isExportMode()) return null;

  return createPortal(
    <div
      className="bn-overlay visible"
      onClick={handleOverlayClick}
      data-testid="bn-export-overlay"
    >
      <div className="bn-modal" data-testid="bn-export-modal" style={{ maxWidth: 420 }}>
        <h2>Export report</h2>
        <p className="bn-modal-subtitle">
          Download a self-contained HTML file that anyone can open in a browser.
        </p>
        <label className="bn-export-checkbox">
          <input
            type="checkbox"
            checked={anonymise}
            onChange={(e) => setAnonymise(e.target.checked)}
            disabled={exporting}
          />
          <span>
            Anonymise participants
            <small className="bn-export-hint">
              Remove participant names, keep codes (p1, p2).
              Moderator names are preserved.
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
            disabled={exporting}
          >
            Cancel
          </button>
          <button
            className="bn-btn bn-btn-primary"
            onClick={handleExport}
            disabled={exporting}
          >
            {exporting ? "Exporting\u2026" : "Export"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
