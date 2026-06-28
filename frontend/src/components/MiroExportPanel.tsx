/**
 * MiroExportPanel — experimental "Send to Miro board" modal.
 *
 * States: loading → connect (OAuth or paste-token) → configure → exporting →
 * done. (Preview was removed — the SVG ≠ the real board and it added a needless
 * decision point; the agnostic board IR + SVG renderer stay for dev/iteration.)
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
import { announce } from "../utils/announce";
import { postStoreMiroToken } from "../shims/bridge";
import {
  getMiroStatus,
  postMiroConnect,
  postMiroDisconnect,
  postMiroExport,
} from "../utils/api";
import type { MiroExportRequest, MiroStatusResponse } from "../utils/types";

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

/**
 * Account holder · team · org, de-duped — lets the user confirm WHICH Miro
 * account/workspace a board will land in (people have personal + client accounts).
 * Personal/free accounts return organization.name == team.name, so drop repeats
 * (case-insensitive, order preserved). Mirrors the macOS sheet's accountText().
 */
function accountLine(s: MiroStatusResponse): string | null {
  const seen = new Set<string>();
  const parts: string[] = [];
  for (const raw of [s.user_name, s.team_name, s.org_name]) {
    const p = raw?.trim();
    if (p && !seen.has(p.toLowerCase())) {
      seen.add(p.toLowerCase());
      parts.push(p);
    }
  }
  return parts.length ? parts.join(" · ") : null;
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
  const [account, setAccount] = useState<string | null>(null);
  const [teamName, setTeamName] = useState<string | null>(null);
  const triggerRef = useRef<Element | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  // On open: remember trigger, fetch connection status.
  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement;
    setError(null);
    setBoardUrl(null);
    setView("loading");
    getMiroStatus()
      .then((s) => {
        setAccount(accountLine(s));
        setTeamName(s.team_name?.trim() || null);
        setView(s.connected ? "configure" : "connect");
      })
      .catch(() => setView("connect"));
  }, [open]);

  // Restore focus on close.
  useEffect(() => {
    if (!open && triggerRef.current instanceof HTMLElement) {
      triggerRef.current.focus();
      triggerRef.current = null;
    }
  }, [open]);

  // Move focus into the dialog on open — the trigger is now inert (useInert),
  // so without this the keyboard/SR user is stranded on document.body behind
  // the inert wall.
  useEffect(() => {
    if (open) requestAnimationFrame(() => headingRef.current?.focus());
  }, [open]);

  // Announce async status transitions — the view swaps the subtitle text with
  // no live region, so a screen-reader user otherwise hears nothing.
  useEffect(() => {
    if (!open) return;
    if (view === "exporting") announce(t("miro.creatingBoard"));
    else if (view === "done") announce(t("miro.boardReady", { count: stickies }));
  }, [open, view, stickies, t]);

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
      if (s.connected) {
        // Persist the validated token natively so it survives an app restart:
        // the sandboxed sidecar can't write the Keychain, so hand it to the
        // macOS host. No-op in browser/serve mode (Python persists it there).
        postStoreMiroToken(token.trim());
        setAccount(accountLine(s));
        setTeamName(s.team_name?.trim() || null);
        setView("configure");
      }
    } catch (e) {
      // Surface the server's reason (invalid token / missing boards:write scope
      // / network) rather than one generic message.
      setError(errDetail(e) || t("miro.connectError"));
    } finally {
      setBusy(false);
    }
  }, [token, t]);

  const handleDisconnect = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      await postMiroDisconnect();
      setAccount(null);
      setTeamName(null);
      setView("connect");
    } catch {
      setError(t("miro.disconnectError"));
    } finally {
      setBusy(false);
    }
  }, [t]);

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

  // Notice naming the destination workspace, with the team picked out (matches
  // the macOS sheet). Plain interpolation + indexOf split — no <Trans> (keeps the
  // bundle under budget); the split positions the <strong> per locale word order.
  const renderNotice = () => {
    const upload = t("miro.uploadNotice");
    if (!teamName) return upload;
    const dest = t("miro.boardDestination", { team: teamName });
    const idx = dest.indexOf(teamName);
    if (idx < 0) return `${dest} ${upload}`;
    return (
      <>
        {dest.slice(0, idx)}
        <strong>{teamName}</strong>
        {dest.slice(idx + teamName.length)} {upload}
      </>
    );
  };

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
      <div
        className="bn-modal"
        data-testid="bn-miro-modal"
        style={{ maxWidth: 460 }}
        role="dialog"
        aria-modal="true"
        aria-labelledby="bn-miro-title"
      >
        <h2 id="bn-miro-title" ref={headingRef} tabIndex={-1}>
          {t("miro.title")}
        </h2>

        {view === "loading" && (
          <p className="bn-modal-subtitle">{t("miro.checkingConnection")}</p>
        )}

        {view === "connect" && (
          <>
            <p className="bn-modal-subtitle">{t("miro.connectIntro")}</p>
            <p className="bn-export-hint" style={{ marginTop: 14 }}>
              {t("miro.orPasteToken")}{" "}
              <a
                href="https://bristlenose.app/docs/send-to-miro.html"
                target="_blank"
                rel="noopener noreferrer"
              >
                {t("miro.howToGetToken")}
              </a>
            </p>
            <input
              type="password"
              value={token}
              placeholder={t("miro.tokenPlaceholder")}
              aria-label={t("miro.tokenPlaceholder")}
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
            {account && <p className="bn-export-hint">{account}</p>}
            <label className="bn-export-hint" htmlFor="bn-miro-board-name">
              {t("miro.boardNameLabel")}
            </label>
            <input
              id="bn-miro-board-name"
              type="text"
              value={boardName}
              placeholder={t("miro.boardNamePlaceholder")}
              onChange={(e) => setBoardName(e.target.value)}
              style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
            />
            <label className="bn-export-hint" style={{ marginTop: 10 }} htmlFor="bn-miro-colour-by">
              {t("miro.colourByLabel")}
            </label>
            <select
              id="bn-miro-colour-by"
              value={colourBy}
              onChange={(e) => setColourBy(e.target.value)}
            >
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
                aria-label={t("miro.linkClipsLabel")}
                onChange={(e) => setClipsBase(e.target.value)}
                style={{ width: "100%", boxSizing: "border-box", padding: "8px 10px" }}
              />
            )}
            <p className="bn-export-hint" style={{ marginTop: 10 }}>
              {renderNotice()}
            </p>
            {error && (
              <p className="bn-export-error" role="alert">
                {error}
              </p>
            )}
            <div className="bn-modal-actions">
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
