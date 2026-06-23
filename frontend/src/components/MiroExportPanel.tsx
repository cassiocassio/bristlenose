/**
 * MiroExportPanel — experimental "Send to Miro board" modal.
 *
 * States: loading → connect (OAuth or paste-token) → configure → exporting →
 * done. A creds-free "Preview" opens the would-be board as HTML in a new tab.
 *
 * Strings are hardcoded English for now (experimental; i18n deferred — see
 * docs/design-miro-bridge.md assumption A4).
 *
 * @module MiroExportPanel
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
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

export function MiroExportPanel({ open, onClose }: MiroExportPanelProps) {
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
      else setError("Token rejected.");
    } catch {
      setError("Could not connect — check the token and try again.");
    } finally {
      setBusy(false);
    }
  }, [token]);

  const handleOAuthConnect = useCallback(async () => {
    setError(null);
    try {
      const { url } = await getMiroAuthUrl();
      window.open(url, "_blank", "noopener,width=600,height=760");
      // Poll for the callback to store the token.
      stopPoll();
      pollRef.current = window.setInterval(async () => {
        try {
          const s = await getMiroStatus();
          if (s.connected) {
            stopPoll();
            setView("configure");
          }
        } catch {
          /* keep polling */
        }
      }, 2000);
    } catch {
      setError("OAuth isn't configured here. Paste an access token instead.");
    }
  }, [stopPoll]);

  const handleDisconnect = useCallback(async () => {
    setBusy(true);
    try {
      await postMiroDisconnect();
      setView("connect");
    } finally {
      setBusy(false);
    }
  }, []);

  const handlePreview = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const { html } = await postMiroPreview(request());
      const blob = new Blob([html], { type: "text/html" });
      window.open(URL.createObjectURL(blob), "_blank", "noopener");
    } catch {
      setError("Could not build the preview.");
    } finally {
      setBusy(false);
    }
  }, [request]);

  const handleExport = useCallback(async () => {
    setView("exporting");
    setError(null);
    try {
      const res = await postMiroExport(request());
      setBoardUrl(res.board_url);
      setStickies(res.stickies);
      setView("done");
    } catch {
      setError("Export failed. Check your connection and try again.");
      setView("configure");
    }
  }, [request]);

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
        <h2>Send to Miro board</h2>

        {view === "loading" && <p className="bn-modal-subtitle">Checking connection…</p>}

        {view === "connect" && (
          <>
            <p className="bn-modal-subtitle">
              Push your quotes onto a new Miro board as sticky notes, grouped by section and
              theme. Connect once — we never touch your existing boards.
            </p>
            <div className="bn-modal-actions" style={{ justifyContent: "flex-start" }}>
              <button className="bn-btn bn-btn-primary" onClick={handleOAuthConnect}>
                Connect with browser
              </button>
            </div>
            <p className="bn-export-hint" style={{ marginTop: 14 }}>
              …or paste a Miro access token:
            </p>
            <input
              type="password"
              value={token}
              placeholder="Miro access token"
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
                Cancel
              </button>
              <button
                className="bn-btn bn-btn-primary"
                onClick={handlePasteConnect}
                disabled={busy || !token.trim()}
              >
                Connect
              </button>
            </div>
          </>
        )}

        {view === "configure" && (
          <>
            <p className="bn-modal-subtitle">
              Connected ✓ ·{" "}
              <button className="bn-linkish" onClick={handleDisconnect} disabled={busy}>
                Disconnect
              </button>
            </p>
            <label className="bn-export-hint">Board name (optional)</label>
            <input
              type="text"
              value={boardName}
              placeholder="Defaults to the project name"
              onChange={(e) => setBoardName(e.target.value)}
              style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
            />
            <label className="bn-export-hint" style={{ marginTop: 10 }}>
              Colour stickies by
            </label>
            <select value={colourBy} onChange={(e) => setColourBy(e.target.value)}>
              <option value="sentiment">Sentiment</option>
              <option value="none">Single colour (yellow)</option>
            </select>
            <label className="bn-export-checkbox" style={{ marginTop: 12 }}>
              <input
                type="checkbox"
                checked={linkClips}
                onChange={(e) => setLinkClips(e.target.checked)}
              />
              <span>
                Link quotes to clips
                <small className="bn-export-hint">
                  Point at the folder where you placed the exported clips.
                </small>
              </span>
            </label>
            {linkClips && (
              <input
                type="text"
                value={clipsBase}
                placeholder="https://drive.google.com/…/clips"
                onChange={(e) => setClipsBase(e.target.value)}
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
              />
            )}
            <p className="bn-export-hint" style={{ marginTop: 10 }}>
              Exports all visible quotes. Data will be uploaded to Miro.
            </p>
            {error && (
              <p className="bn-export-error" role="alert">
                {error}
              </p>
            )}
            <div className="bn-modal-actions">
              <button className="bn-btn bn-btn-secondary" onClick={handlePreview} disabled={busy}>
                Preview
              </button>
              <button className="bn-btn bn-btn-primary" onClick={handleExport} disabled={busy}>
                Create board
              </button>
            </div>
          </>
        )}

        {view === "exporting" && <p className="bn-modal-subtitle">Creating board…</p>}

        {view === "done" && (
          <>
            <p className="bn-modal-subtitle">
              Board ready — {stickies} quote sticky{stickies === 1 ? "" : "s"} placed.
            </p>
            <div className="bn-modal-actions">
              <button className="bn-btn bn-btn-secondary" onClick={onClose}>
                Done
              </button>
              {boardUrl && (
                <a
                  className="bn-btn bn-btn-primary"
                  href={boardUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open in Miro ↗
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
