/**
 * FigJamExportPanel — "Send to FigJam": download a board file for the
 * Bristlenose FigJam plugin.
 *
 * FigJam has no way for an outside app to write to a board, so this is a
 * download, not a push: Bristlenose writes the file, and the researcher opens
 * it with the plugin inside FigJam (docs/design-board-integrations.md). No
 * connection, so two views: the choices, then the steps to finish in FigJam.
 *
 * The choices are the Miro export's, and reuse its strings, so the two boards
 * offer the same things: the board name (arriving filled with the project's —
 * owner, 17 Oct 2026), "break long quotes" (ticked), the sticky shape (square
 * by default on FigJam), and clip links (parked: `featureFlags.boardClipLinks`).
 *
 * Parked behind `featureFlags.figjamExport` until the plugin is published.
 *
 * @module FigJamExportPanel
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useInert } from "../hooks/useInert";
import { Icon } from "./Icon";
import { PanelErrorBoundary } from "./PanelErrorBoundary";
import { isExportMode } from "../utils/exportData";
import { featureFlags } from "../utils/featureFlags";
import { announce } from "../utils/announce";
import { apiGet, figjamBoardDownloadUrl, getFigJamBoard } from "../utils/api";
import type { ApiError, FigJamBoardRequest } from "../utils/api";
import { resolveBrowserLang } from "../i18n/LocaleStore";

interface FigJamExportPanelProps {
  open: boolean;
  onClose: () => void;
}

type View = "configure" | "preparing" | "ready";

/** Server `reason` → the sentence that says it in the reader's language. */
const ERROR_KEYS: Record<string, string> = {
  no_quotes_selected: "miro.errNoQuotesSelected",
  clips_base_not_http: "figjam.errClipsBase",
};

export function FigJamExportPanel({ open, onClose }: FigJamExportPanelProps) {
  const { t, i18n } = useTranslation();
  useInert(open);
  const [view, setView] = useState<View>("configure");
  const [boardName, setBoardName] = useState("");
  const [splitLong, setSplitLong] = useState(true);
  const [shape, setShape] = useState<"square" | "rectangle">("square");
  const [linkClips, setLinkClips] = useState(false);
  const [clipsBase, setClipsBase] = useState("");
  const [quotes, setQuotes] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const named = useRef(false); // the researcher has typed a name: don't overwrite it
  const triggerRef = useRef<Element | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // On open: start over, and fill the name with the project's, so nothing
  // arrives on a board untitled.
  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement;
    setView("configure");
    setError(null);
    if (!named.current) {
      apiGet<{ project_name: string }>("/info")
        .then((info) => {
          if (!named.current) setBoardName(info.project_name ?? "");
        })
        .catch(() => undefined);
    }
    requestAnimationFrame(() => (headingRef.current ?? document.getElementById("bn-figjam-title"))?.focus());
  }, [open]);

  // Restore focus on close.
  useEffect(() => {
    if (!open && triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
      triggerRef.current = null;
    }
  }, [open]);

  // Escape closes.
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

  const request = useCallback(
    (): FigJamBoardRequest => ({
      board_name: boardName.trim(),
      // A raw region tag (`en-GB`) would fall back to English on the server.
      locale: resolveBrowserLang(i18n.language) ?? "en",
      split_long_quotes: splitLong,
      sticky_shape: shape,
      clips_base: featureFlags.boardClipLinks && linkClips ? clipsBase.trim() : "",
    }),
    [boardName, splitLong, shape, linkClips, clipsBase, i18n.language],
  );

  const handleDownload = useCallback(async () => {
    setError(null);
    setView("preparing");
    const req = request();
    try {
      // Build it once to read its counts and catch a refusal here, in words,
      // rather than have the browser save the refusal as a file.
      const summary = await getFigJamBoard(req);
      setQuotes(summary.totals.quotes);
      const a = document.createElement("a");
      a.href = figjamBoardDownloadUrl(req);
      a.download = "";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setView("ready");
      announce(t("figjam.downloading", { count: summary.totals.quotes }));
    } catch (e) {
      const reason = (e as ApiError)?.reason ?? "";
      setError(t(ERROR_KEYS[reason] ?? "figjam.error"));
      setView("configure");
    }
  }, [request, t]);

  if (isExportMode()) return null;

  return createPortal(
    // Modal backdrop. It never closes the dialog: Escape and the dialog's own buttons do (decided 24 Oct 2026).
    <div
      className={`bn-overlay${open ? " visible" : ""}`}
      aria-hidden={!open}
      data-testid="bn-figjam-overlay"
    >
      <div
        className="bn-modal"
        data-testid="bn-figjam-modal"
        style={{ maxWidth: 460 }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bn-figjam-title"
      >
        {/* Outside the boundary, so a dialog whose content crashed still has a way out with the mouse. */}
        <button className="bn-modal-close" onClick={onClose} aria-label={t("buttons.close")}>
          <Icon name="close" decorative />
        </button>
        {/* If the content crashes, the mark takes the heading's id and so names the dialog. */}
        <PanelErrorBoundary part labelId="bn-figjam-title">
          {() => (
            <>
              <h2 id="bn-figjam-title" ref={headingRef} tabIndex={-1}>
                {t("figjam.title")}
              </h2>

              {view !== "ready" && (
                <>
                  <p className="bn-modal-subtitle">{t("figjam.intro")}</p>
                  <label className="bn-export-hint" htmlFor="bn-figjam-board-name">
                    {t("miro.boardNameLabel")}
                  </label>
                  <input
                    id="bn-figjam-board-name"
                    type="text"
                    value={boardName}
                    onChange={(e) => {
                      named.current = true;
                      setBoardName(e.target.value);
                    }}
                    style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                  />
                  <label className="bn-export-checkbox" style={{ marginTop: 12 }}>
                    <input
                      type="checkbox"
                      checked={splitLong}
                      onChange={(e) => setSplitLong(e.target.checked)}
                      data-testid="bn-figjam-split-long"
                    />
                    <span>{t("miro.splitLongQuotes")}</span>
                  </label>
                  <fieldset className="bn-export-radios" data-testid="bn-figjam-shape">
                    <legend className="bn-export-hint">{t("miro.stickyShape")}</legend>
                    {(["square", "rectangle"] as const).map((s) => (
                      <label key={s} className="bn-export-checkbox">
                        <input
                          type="radio"
                          name="bn-figjam-shape"
                          value={s}
                          checked={shape === s}
                          onChange={() => setShape(s)}
                        />
                        <span>{t(s === "square" ? "miro.stickyShapeSquare" : "miro.stickyShapeRectangle")}</span>
                      </label>
                    ))}
                  </fieldset>
                  {featureFlags.boardClipLinks && (
                  <label className="bn-export-checkbox" style={{ marginTop: 12 }}>
                    <input
                      type="checkbox"
                      checked={linkClips}
                      onChange={(e) => setLinkClips(e.target.checked)}
                    />
                    <span>
                      {t("miro.linkClipsLabel")}
                      <small className="bn-export-hint">{t("miro.linkClipsHint")}</small>
                    </span>
                  </label>
                  )}
                  {featureFlags.boardClipLinks && linkClips && (
                    <input
                      type="text"
                      value={clipsBase}
                      placeholder={t("miro.clipsBasePlaceholder")}
                      aria-label={t("miro.linkClipsLabel")}
                      onChange={(e) => setClipsBase(e.target.value)}
                      style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
                    />
                  )}
                  <p className="bn-export-hint" style={{ marginTop: 10 }}>
                    {t("figjam.notice")}
                  </p>
                  {error && (
                    <p className="bn-export-error" role="alert">
                      {error}
                    </p>
                  )}
                  <div className="bn-modal-actions">
                    <button className="bn-btn bn-btn-secondary" onClick={onClose}>
                      {t("miro.cancel")}
                    </button>
                    <button
                      className="bn-btn bn-btn-primary"
                      onClick={handleDownload}
                      disabled={view === "preparing"}
                      data-testid="bn-figjam-download"
                    >
                      {view === "preparing" ? t("figjam.preparing") : t("figjam.download")}
                    </button>
                  </div>
                </>
              )}

              {view === "ready" && (
                <>
                  {/* "Downloading", not "saved": the browser or the Mac's save panel
                      owns that, and the researcher can still cancel it. */}
                  <p className="bn-modal-subtitle">{t("figjam.downloading", { count: quotes })}</p>
                  <p className="bn-export-hint">{t("figjam.nextSteps")}</p>
                  <ol className="bn-export-hint" data-testid="bn-figjam-steps">
                    <li>{t("figjam.step1")}</li>
                    <li>{t("figjam.step2")}</li>
                    <li>{t("figjam.step3")}</li>
                  </ol>
                  <div className="bn-modal-actions">
                    <button className="bn-btn bn-btn-primary" onClick={onClose}>
                      {t("miro.done")}
                    </button>
                  </div>
                </>
              )}
            </>
          )}
        </PanelErrorBoundary>
      </div>
    </div>,
    document.body,
  );
}
