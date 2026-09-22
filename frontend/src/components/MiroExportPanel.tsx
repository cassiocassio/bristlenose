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
import { resolveBrowserLang } from "../i18n/LocaleStore";
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
 * Server `reason` → the key that says it in the reader's language.
 *
 * `api.ts` is explicit that `detail` is "English prose. Do not display it to a
 * researcher" — and this panel displayed it, because until the server carried a
 * discriminator there was nothing else to show. A table, not a `includes()` on
 * the sentence: matching English prose breaks the day somebody rewords it.
 *
 * An unknown or absent reason falls through to `detail`, so an older sidecar
 * behaves exactly as it did before.
 */
const EXPORT_ERROR_KEYS: Record<string, string> = {
  no_quotes_selected: "miro.errNoQuotesSelected",
  no_board_id: "miro.errNoBoardId",
  board_incomplete: "miro.errBoardIncomplete",
};

/** The localised sentence when the server named a reason, else "". */
function errReasonKey(e: unknown): string {
  const r = (e as { reason?: unknown })?.reason;
  return typeof r === "string" ? (EXPORT_ERROR_KEYS[r] ?? "") : "";
}

/** One of the server's `vars` for a reason, else "". */
function errVar(e: unknown, name: string): string {
  const v = (e as { vars?: Record<string, unknown> })?.vars?.[name];
  return typeof v === "string" ? v : "";
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
  const { t, i18n } = useTranslation();
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

  // Normalise through resolveBrowserLang for the same reason the HTML export
  // does: `i18n.language` can be a raw region tag (`en-GB`, `zh-TW`) that the
  // server's SUPPORTED_LOCALES check rejects, silently falling the board back
  // to English — the exact failure this send exists to end.
  const request = useCallback(
    (): MiroExportRequest => ({
      board_name: boardName.trim() || null,
      colour_by: colourBy,
      clips_base: linkClips ? clipsBase.trim() : "",
      locale: resolveBrowserLang(i18n.language) ?? "en",
    }),
    [boardName, colourBy, linkClips, clipsBase, i18n.language],
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
      // Prefer the localised sentence the server's `reason` names. The partial-
      // board case keeps its recovery URL: the board IS half-built, and hiding
      // where it went orphans it behind a generic "try again" — so that key's
      // copy tells the researcher to open it, and the address the server sent
      // in `vars.url` follows the sentence (the raw detail used to carry it,
      // and still does when the reason is one this build does not know).
      const key = errReasonKey(e);
      const url = errVar(e, "url");
      setError(key ? (url ? `${t(key)} ${url}` : t(key)) : errDetail(e) || t("miro.exportError"));
      setView("configure");
    }
  }, [request, t]);

  // Notice naming the destination workspace, with the team picked out (matches
  // the macOS sheet). Split the RAW template on the {{team}} placeholder (no
  // interpolation) so the <strong> lands on the slot regardless of the team's
  // text — a team literally named "board"/"new" can't mis-split. Same approach as
  // MiroSheet.swift's range(of: "{{team}}"); no <Trans> (keeps the bundle under
  // the size gate). The placeholder slot positions the emphasis per locale order.
  const renderNotice = () => {
    const upload = t("miro.uploadNotice");
    if (!teamName) return upload;
    const template = t("miro.boardDestination"); // raw, contains "{{team}}"
    const slot = template.indexOf("{{team}}");
    if (slot < 0) return `${template} ${upload}`;
    return (
      <>
        {template.slice(0, slot)}
        <strong>{teamName}</strong>
        {template.slice(slot + "{{team}}".length)} {upload}
      </>
    );
  };

  if (isExportMode()) return null;

  return createPortal(
    // Modal backdrop; click-outside-to-close. Escape handled by the modal's keydown elsewhere.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
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
