/**
 * ExportDialog — modal for exporting a self-contained HTML report.
 *
 * Triggered from the NavBar export button.  Options: anonymise checkbox.
 * Calls the server export endpoint and triggers a file download.
 *
 * @module ExportDialog
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Dialog } from "./Dialog";
import { PanelErrorBoundary } from "./PanelErrorBoundary";
import { useProjectId } from "../hooks/useProjectId";
import { isExportMode } from "../utils/exportData";
import { resolveBrowserLang } from "../i18n/LocaleStore";
import { LOCALE_LABELS } from "../i18n/localeLabels";
import { SUPPORTED_LOCALES, type Locale } from "../i18n";

interface ExportDialogProps {
  open: boolean;
  onClose: () => void;
  /** Pre-select the anonymise checkbox when opening (e.g. from Export Anonymised menu). */
  initialAnonymise?: boolean;
}

export function ExportDialog({ open, onClose, initialAnonymise = false }: ExportDialogProps) {
  const { t, i18n } = useTranslation();
  const projectId = useProjectId();
  const [anonymise, setAnonymise] = useState(false);
  // Defaults to the researcher's own language, which is what the export has
  // baked since 30c5c2f7. Stated rather than silent so they can SEE which
  // language they are about to hand a client — a researcher running the UI in
  // a machine-seeded locale pending native review would otherwise never know.
  const [exportLocale, setExportLocale] = useState<Locale>("en");
  const [error, setError] = useState<string | null>(null);

  // Reset state when opening. Escape, focus and the page behind are Dialog's.
  useEffect(() => {
    if (open) {
      setAnonymise(initialAnonymise);
      setExportLocale(resolveBrowserLang(i18n.language) ?? "en");
      setError(null);
    }
  }, [open]);

  const handleExport = useCallback(() => {
    // Direct anchor navigation — no fetch, no blob.  The auth cookie set on
    // the SPA HTML response carries the bearer token; the server replies
    // with `Content-Disposition: attachment` and (in the desktop app)
    // WKDownload routes the bytes through NSSavePanel.  In the browser the
    // native download UI takes over.
    setError(null);
    // Bake the researcher's current UI language, normalised to a supported token
    // (see AppLayout.triggerReportDownload).
    const params = new URLSearchParams();
    if (anonymise) params.set("anonymise", "true");
    params.set("locale", exportLocale);
    const url = `/api/projects/${projectId}/export?${params.toString()}`;
    const a = document.createElement("a");
    a.href = url;
    a.download = "";  // hint download intent; server's Content-Disposition wins
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    onClose();
  }, [anonymise, exportLocale, onClose, projectId]);

  if (isExportMode()) return null;

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="bn-export-modal"
      testId="bn-export-overlay"
      modalTestId="bn-export-modal"
      labelledBy="bn-export-title"
    >
        {/* If the content crashes, the mark takes the heading's id and so names the dialog. */}
        <PanelErrorBoundary part labelId="bn-export-title">
          {() => (
            <>
              <h2 id="bn-export-title">{t("export.heading")}</h2>
              <p className="bn-modal-subtitle">
                {t("export.subtitle")}
              </p>
              <label className="bn-export-locale">
                <span>{t("settings:language.legend")}</span>
                <select
                  className="bn-locale-select"
                  value={exportLocale}
                  onChange={(e) => setExportLocale(e.target.value as Locale)}
                  data-testid="bn-export-locale-select"
                >
                  {SUPPORTED_LOCALES.map((loc) => (
                    <option key={loc} value={loc}>
                      {LOCALE_LABELS[loc]}
                    </option>
                  ))}
                </select>
              </label>
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
            </>
          )}
        </PanelErrorBoundary>
    </Dialog>
  );
}
