/**
 * MiroExportPanel — experimental "Send to Miro board" modal.
 *
 * States: loading → connect (OAuth or paste-token) → configure → exporting →
 * done. A creds-free "Preview" opens the would-be board as HTML in a new tab.
 *
 * Strings live under the `miro.*` namespace in common.json.
 *
 * @module MiroExportPanel
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import { useInert } from "../hooks/useInert";
import { isExportMode } from "../utils/exportData";
import {
  getMiroAuthUrl,
  getMiroStatus,
  postMiroConnect,
  postMiroDisconnect,
  postMiroExport,
  postMiroPreview,
} from "../utils/api";
import type { MiroExportRequest } from "../utils/types";

interface MiroExportPanelProps {
  open: boolean;
  onClose: () => void;
}

type View = "loading" | "connect" | "configure" | "exporting" | "done";

/** Pull the server `detail` (attached by api.ts httpError) off a caught error. */
function errDetail(e: unknown): string {
  return typeof (e as { detail?: unknown })?.detail === "string"
    ? (e as { detail: string }).detail
    : "";
}

export function MiroExportPanel({ open, onClose }: MiroExportPanelProps) {
  const { t } = useTranslation();
  useInert(open);
  const [view, setView] = useState<View>("loading");
  const [token, setToken] = useState("");
  const [boardName, setBoardName] = useState("");
  const [colourBy, setColourBy] = useState("sentiment");
  const [linkClips, setLinkClips] = useState(false);
  const [clipsBase, setClipsBase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [boardUrl, setBoardUrl] = useState<string | null>(null);
  const [stickies, setStickies] = useState(0);
  const pollRef = useRef<number | null>(null);
  const triggerRef = useRef<Element | null>(null);

  const stopPoll = useCallback(() => {
    if (pollRef.current !== null) {
      window.clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  // On open: remember trigger, fetch connection status.
  useEffect(() => {
    if (!open) {
      stopPoll();
      return;
    }
    triggerRef.current = document.activeElement;
    setError(null);
    setBoardUrl(null);
    setView("loading");
    getMiroStatus()
      .then((s) => setView(s.connected ? "configure" : "connect"))
      .catch(() => setView("connect"));
    return stopPoll;
  }, [open, stopPoll]);

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
    (): MiroExportRequest => ({
      board_name: boardName.trim() || null,
      colour_by: colourBy,
      clips_base: linkClips ? clipsBase.trim() : "",
    }),
    [boardName, colourBy, linkClips, clipsBase],
  );

  const handlePasteConnect = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const s = await postMiroConnect(token.trim());
      if (s.connected) setView("configure");
    } catch (e) {
      // Surface the server's reason (invalid token / missing boards:write scope
      // / network) rather than one generic message.
      setError(errDetail(e) || t("miro.connectError"));
    } finally {
      setBusy(false);
    }
  }, [token, t]);

  const handleOAuthConnect = useCallback(async () => {
    setError(null);
    try {
      const { url } = await getMiroAuthUrl();
      window.open(url, "_blank", "noopener,width=600,height=760");
      // Poll for the callback to store the token — capped so it can't spin
      // forever if the user dismisses the consent window.
      stopPoll();
      let attempts = 0;
      pollRef.current = window.setInterval(async () => {
        attempts += 1;
        if (attempts > 60) {
          stopPoll();
          setError(t("miro.oauthTimeout"));
          return;
        }
        try {
          const s = await getMiroStatus();
          if (s.connected) {
            stopPoll();
            setView("configure");
          }
        } catch {
          /* transient; keep polling until the cap */
        }
      }, 2000);
    } catch {
      setError(t("miro.oauthUnconfigured"));
    }
  }, [stopPoll, t]);

  const handleDisconnect = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await postMiroDisconnect();
      setView("connect");
    } catch {
      setError(t("miro.disconnectError"));
    } finally {
      setBusy(false);
    }
  }, [t]);

  const handlePreview = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const { html } = await postMiroPreview(request());
      const blob = new Blob([html], { type: "text/html" });
      window.open(URL.createObjectURL(blob), "_blank", "noopener");
    } catch {
      setError(t("miro.previewError"));
    } finally {
      setBusy(false);
    }
  }, [request, t]);

  const handleExport = useCallback(async () => {
    setView("exporting");
    setError(null);
    try {
      const res = await postMiroExport(request());
      setBoardUrl(res.board_url);
      setStickies(res.stickies);
      setView("done");
    } catch (e) {
      // On a partial-board 502 the detail carries the recovery URL ("Board
      // created but incomplete — open it: <url>"); surface it so the half-built
      // board isn't orphaned behind a generic "try again".
      setError(errDetail(e) || t("miro.exportError"));
      setView("configure");
    }
  }, [request, t]);

  if (isExportMode()) return null;

  return createPortal(
    <div
      className={`bn-overlay${open ? " visible" : ""}`}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      aria-hidden={!open}
      data-testid="bn-miro-overlay"
    >
      <div className="bn-modal" data-testid="bn-miro-modal" style={{ maxWidth: 460 }}>
        <h2>{t("miro.title")}</h2>

        {view === "loading" && (
          <p className="bn-modal-subtitle">{t("miro.checkingConnection")}</p>
        )}

        {view === "connect" && (
          <>
            <p className="bn-modal-subtitle">{t("miro.connectIntro")}</p>
            <div className="bn-modal-actions" style={{ justifyContent: "flex-start" }}>
              <button className="bn-btn bn-btn-primary" onClick={handleOAuthConnect}>
                {t("miro.connectWithBrowser")}
              </button>
            </div>
            <p className="bn-export-hint" style={{ marginTop: 14 }}>
              {t("miro.orPasteToken")}
            </p>
            <input
              type="password"
              value={token}
              placeholder={t("miro.tokenPlaceholder")}
              onChange={(e) => setToken(e.target.value)}
              style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
            />
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
                onClick={handlePasteConnect}
                disabled={busy || !token.trim()}
              >
                {t("miro.connect")}
              </button>
            </div>
          </>
        )}

        {view === "configure" && (
          <>
            <p className="bn-modal-subtitle">
              {t("miro.connected")} ·{" "}
              <button className="bn-linkish" onClick={handleDisconnect} disabled={busy}>
                {t("miro.disconnect")}
              </button>
            </p>
            <label className="bn-export-hint">{t("miro.boardNameLabel")}</label>
            <input
              type="text"
              value={boardName}
              placeholder={t("miro.boardNamePlaceholder")}
              onChange={(e) => setBoardName(e.target.value)}
              style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
            />
            <label className="bn-export-hint" style={{ marginTop: 10 }}>
              {t("miro.colourByLabel")}
            </label>
            <select value={colourBy} onChange={(e) => setColourBy(e.target.value)}>
              <option value="sentiment">{t("miro.colourBySentiment")}</option>
              <option value="none">{t("miro.colourByNone")}</option>
            </select>
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
            {linkClips && (
              <input
                type="text"
                value={clipsBase}
                placeholder={t("miro.clipsBasePlaceholder")}
                onChange={(e) => setClipsBase(e.target.value)}
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
              />
            )}
            <p className="bn-export-hint" style={{ marginTop: 10 }}>
              {t("miro.uploadNotice")}
            </p>
            {error && (
              <p className="bn-export-error" role="alert">
                {error}
              </p>
            )}
            <div className="bn-modal-actions">
              <button className="bn-btn bn-btn-secondary" onClick={handlePreview} disabled={busy}>
                {t("miro.preview")}
              </button>
              <button className="bn-btn bn-btn-primary" onClick={handleExport} disabled={busy}>
                {t("miro.createBoard")}
              </button>
            </div>
          </>
        )}

        {view === "exporting" && (
          <p className="bn-modal-subtitle">{t("miro.creatingBoard")}</p>
        )}

        {view === "done" && (
          <>
            <p className="bn-modal-subtitle">{t("miro.boardReady", { count: stickies })}</p>
            <div className="bn-modal-actions">
              <button className="bn-btn bn-btn-secondary" onClick={onClose}>
                {t("miro.done")}
              </button>
              {boardUrl && (
                <a
                  className="bn-btn bn-btn-primary"
                  href={boardUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {t("miro.openInMiro")}
                </a>
              )}
            </div>
          </>
        )}
      </div>
    </div>,
    document.body,
  );
}
