/**
 * MiroExportPanel — "Send to Miro" for the quotes board, and the screens board's "Send to Miro
 * board".
 *
 * The quotes board has two routes, as tabs (owner, 9 Nov 2026;
 * docs/mockups/miro-board-file-route.html). **Miro app**, always the tab it opens on: copy or
 * download the board file, which the Bristlenose app inside Miro draws (miro-app/,
 * docs/design-miro-in-board-app.md) — no sign-in, no token. **Developer access token**: the push
 * through Miro's REST API with the researcher's own token, kept for keen beta testers and, later,
 * for a relay (parked). The screens board has only the token route: a board file carries no
 * screengrabs.
 *
 * Token route states: loading → connect (paste-token) → configure → exporting →
 * done. (Preview was removed — the SVG ≠ the real board and it added a needless
 * decision point; the agnostic board IR + SVG renderer stay for dev/iteration.)
 *
 * Strings live under the `miro.*` namespace in common.json.
 *
 * @module MiroExportPanel
 */

import { useCallback, useEffect, useEffectEvent, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Dialog } from "./Dialog";
import { SegmentedTabs } from "./SegmentedTabs";
import { PanelErrorBoundary } from "./PanelErrorBoundary";
import { isExportMode } from "../utils/exportData";
import { featureFlags } from "../utils/featureFlags";
import { isDesktop } from "../utils/platform";
import { announce } from "../utils/announce";
import { postStoreMiroToken } from "../shims/bridge";
import {
  apiGet,
  cancelMiroBoard,
  cancelScreensMiro,
  figjamBoardDownloadUrl,
  getFigJamBoard,
  getMiroBoardStatus,
  getMiroStatus,
  getScreensMiroStatus,
  postMiroConnect,
  postMiroDisconnect,
  startMiroBoard,
  startScreensMiro,
} from "../utils/api";
import type { ApiError, FigJamBoardRequest } from "../utils/api";
import { copyBoardToClipboard } from "../utils/boardClipboard";
import type { BoardFile } from "../utils/boardClipboard";
import { resolveBrowserLang } from "../i18n/LocaleStore";
import type {
  MiroBoardBuild,
  MiroBoardStatus,
  MiroExportRequest,
  MiroStatusResponse,
  MiroStoreKind,
  ScreensMiroStatus,
} from "../utils/types";

interface MiroExportPanelProps {
  open: boolean;
  onClose: () => void;
  /** Opened on the Screens lens: build the screens board, a frame per screengrab
   *  (docs/design-screens-export.md §6), not the quotes board. */
  screens?: boolean;
}

/** How often a board's progress is read while it is built (both boards are jobs). */
const BOARD_POLL_MS = 1500;

type View = "loading" | "connect" | "configure" | "exporting" | "done";

type Route = "app" | "token";

/** The Bristlenose app's install page on Miro (its Installation URL): pick a team, Add & allow.
 *  Shared by link on purpose; a company admin approves the app by the client ID in it. */
const MIRO_APP_INSTALL_URL =
  "https://miro.com/app-install/?response_type=code&client_id=3458764676772092122&redirect_uri=%2Fapp-install%2Fconfirm%2F";

/** Each route's help page, opened by the round "?" (the Mac sheet's HelpLink does the same). */
const HELP_URL: Record<Route, string> = {
  app: "https://bristlenose.app/docs/miro-app.html",
  token: "https://bristlenose.app/docs/send-to-miro.html",
};

/** A board file refused by the server, in the reader's words (the FigJam panel's table). */
const BOARD_FILE_ERROR_KEYS: Record<string, string> = {
  no_quotes_selected: "miro.errNoQuotesSelected",
};

/**
 * A sentence with controls in it ("Either {{download}} or {{copy}}"): split the raw template on
 * its placeholders and put each control in its slot, so a language can reorder them. The same
 * approach as `renderNotice` below, for the same reason (no `<Trans>`, and a value can't mis-split).
 */
function withSlots(template: string, slots: Record<string, ReactNode>): ReactNode[] {
  return template.split(/\{\{(\w+)\}\}/).map((part, i) =>
    i % 2 === 1 ? <span key={i}>{slots[part] ?? null}</span> : part,
  );
}

/**
 * "Connected, but couldn't save the token to <store>" in each store's own word: the Mac's
 * Keychain, the Linux desktop's keyring, or the settings file Bristlenose falls back to.
 * One key per store, not a `{{store}}` placeholder, because the noun declines and agrees
 * with its article in half the locales. Literal keys, so the locale-reader gate sees each.
 */
const PERSIST_WARNING_KEY: Record<MiroStoreKind, string> = {
  keychain: "miro.persistWarningKeychain",
  secret_service: "miro.persistWarningKeyring",
  file: "miro.persistWarningFile",
};

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
 * Both boards are jobs (18 Oct 2026), and a job's status carries a reason, never
 * prose: an unknown or absent one reads as `miro.exportError`.
 */
const EXPORT_ERROR_KEYS: Record<string, string> = {
  token_rejected: "miro.tokenRejected",
  not_connected: "miro.errNotConnected",
  no_quotes_selected: "miro.errNoQuotesSelected",
  no_board_id: "miro.errNoBoardId",
  board_incomplete: "miro.errBoardIncomplete",
  no_stills: "export.screens.none",
};

type Translate = ReturnType<typeof useTranslation>["t"];

/**
 * What a build's line says. A count rather than a percentage, because a count is the question a
 * glance asks; Miro's own waits are said as waiting, except while the board is opening, whose line
 * already explains the wait (Miro refuses a new board's frames for about half a minute).
 */
function buildLine(t: Translate, b: MiroBoardBuild | null): string {
  if (!b) return t("miro.creatingBoard");
  if (b.waiting && b.phase !== "opening") return t("miro.progressWaiting");
  const counts = { done: b.count_done, total: b.count_total };
  switch (b.phase) {
    case "preparing":
      return t("miro.progressPreparing", counts);
    case "opening":
      return t("miro.progressOpening");
    case "quotes":
      return t("miro.progressQuotes", counts);
    case "groups":
      // No long quote to group: only the title is left, a single call.
      return b.count_total ? t("miro.progressGroups", counts) : t("miro.creatingBoard");
    case "screens":
      return t("miro.progressScreens", counts);
    default:
      return t("miro.creatingBoard");
  }
}

/**
 * Time left in whole minutes, "<1 min" under one — the Mac sheet's `RunProgressSubtitle.etaText`,
 * so both say the same. Nothing until the server has earned an estimate.
 */
function etaLine(t: Translate, seconds: number | null | undefined): string | null {
  if (seconds == null || !(seconds > 0)) return null;
  if (seconds < 60) return t("miro.etaUnderMinute");
  return t("miro.etaMinutes", { count: Math.max(1, Math.round(seconds / 60)) });
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

export function MiroExportPanel({ open, onClose, screens = false }: MiroExportPanelProps) {
  const { t, i18n } = useTranslation();
  const [view, setView] = useState<View>("loading");
  const [token, setToken] = useState("");
  const [boardName, setBoardName] = useState("");
  const named = useRef(false); // the researcher has typed a name: don't overwrite it
  // Flat by default on every board (owner, 19 Oct 2026); sentiment is offered.
  const [colourBy, setColourBy] = useState("none");
  const [linkClips, setLinkClips] = useState(false);
  // On by default — it is the right thing for a long quote — and shown, so a researcher arriving
  // at the board knows why a quote runs over two or three stickies (owner, 17 Oct 2026).
  const [splitLong, setSplitLong] = useState(true);
  // Rectangle by default: a dense board, a quote in longer lines. Square is offered — "users will
  // want to pick" (owner, 17 Oct 2026).
  const [shape, setShape] = useState<"rectangle" | "square">("rectangle");
  const [clipsBase, setClipsBase] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Connected, but the token wasn't saved: state beside "Connected ✓", not an error.
  const [persistWarning, setPersistWarning] = useState<string | null>(null);
  const [boardUrl, setBoardUrl] = useState<string | null>(null);
  const [stickies, setStickies] = useState(0);
  // Both boards are jobs: how far the build has got, how many screens it could not show, and
  // which build this panel is waiting on (closing or a new build stops the old wait).
  const [buildState, setBuildState] = useState<MiroBoardBuild | null>(null);
  const [skipped, setSkipped] = useState(0);
  const build = useRef(0);
  const [account, setAccount] = useState<string | null>(null);
  const [teamName, setTeamName] = useState<string | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);
  // The quotes board's route. Always opens on the Miro app, even for someone connected with a
  // token: it is the better route (owner, 9 Nov 2026). The screens board has only the token route.
  const [route, setRoute] = useState<Route>("app");
  const tab: Route = screens ? "token" : route;
  // The Miro app route: "Copied" in the button's place, the download's line, or why neither worked.
  // Each is kept with the choices it was made under, and holds only while they still hold: a
  // changed choice makes a different board.
  const [copiedFor, setCopiedFor] = useState<string | null>(null);
  const [downloadedFor, setDownloadedFor] = useState<{ choices: string; quotes: number } | null>(null);
  const [fileBusy, setFileBusy] = useState(false);
  const [fileError, setFileError] = useState<string | null>(null);
  // Which opening a copy or download belongs to: closing moves it on, so a slow one that answers
  // after the panel was shut and opened again says nothing into the new opening.
  const opening = useRef(0);

  /**
   * Read a build until it ends. Both boards are jobs: the quotes board because Miro refuses a new
   * board's frames for about half a minute and every sticky batch is a round trip, the screens
   * board because a screenshot per frame is made and uploaded. Their failures carry the same
   * reasons; a board left part-built names its address, so it is never orphaned behind "try
   * again".
   */
  const watch = useCallback(
    async (mine: number) => {
      const live = () => mine === build.current;
      const read: () => Promise<ScreensMiroStatus | MiroBoardStatus> = screens
        ? getScreensMiroStatus
        : getMiroBoardStatus;
      try {
        let s = await read();
        while (live() && s.status === "running") {
          setBuildState(s.build ?? null);
          await new Promise((r) => setTimeout(r, BOARD_POLL_MS));
          if (!live()) return;
          s = await read();
        }
        if (!live()) return;
        if (s.status === "cancelled") {
          setView("configure");
          return;
        }
        if (s.status === "idle") {
          // The server no longer knows the build (it restarted): say so rather than nothing.
          setError(t("miro.exportError"));
          setView("configure");
          return;
        }
        if (s.status !== "completed") {
          const key = EXPORT_ERROR_KEYS[s.reason ?? ""] ?? "miro.exportError";
          setError(s.board_url ? `${t(key)} ${s.board_url}` : t(key));
          setView("configure");
          return;
        }
        if (!s.board_url) {
          // A board with no link is not ready: Open in Miro would do nothing (R79).
          setError(t("miro.exportError"));
          setView("configure");
          return;
        }
        setBoardUrl(s.board_url);
        if ("completed_count" in s) {
          setStickies(s.completed_count);
          setSkipped(s.skipped_count);
        } else {
          setStickies(s.stickies);
        }
        setView("done");
      } catch {
        if (!live()) return;
        setError(t("miro.exportError"));
        setView("configure");
      }
    },
    [screens, t],
  );
  // An event, not a dependency: a language change re-creates `watch` (it closes over `t`), and
  // the open effect must not re-run for that — it would reset a finished panel to loading.
  const resume = useEffectEvent(() => {
    void watch(++build.current);
  });
  // A status read that failed is not "signed out" (R78): the Connect step stays, its error line
  // says why. `httpError` attaches the HTTP status; a fetch that never reached the server has none.
  // An event for the same reason as `resume`: it reads `t`.
  const statusFailed = useEffectEvent((e: unknown) => {
    const s = (e as { status?: unknown })?.status;
    setError(typeof s === "number" ? t("miro.requestFailed", { status: s }) : t("miro.serverUnreachable"));
    setView((v) => (v === "loading" ? "connect" : v));
  });

  // On open: remember trigger, fetch connection status.
  useEffect(() => {
    if (!open) return;
    setError(null);
    setPersistWarning(null);
    setBoardUrl(null);
    setSkipped(0);
    setBuildState(null);
    setView("loading");
    setRoute("app");
    setCopiedFor(null);
    setDownloadedFor(null);
    setFileError(null);
    setFileBusy(false);
    // Which build this opening may pick up: closing the panel before the reads come back moves
    // `build.current` on, and nothing then starts polling behind a shut panel.
    const mine = build.current;
    // Set once the status has answered: a later failure (the running-board read) is not one.
    let answered = false;
    getMiroStatus()
      .then((s) => {
        setAccount(accountLine(s));
        setTeamName(s.team_name?.trim() || null);
        setView(s.connected ? "configure" : "connect");
        answered = true;
        if (!s.connected) return;
        if (mine !== build.current) return;
        // A board still being built when the panel was closed is picked up again, not lost.
        return (screens ? getScreensMiroStatus : getMiroBoardStatus)().then((b) => {
          if (mine !== build.current || b.status !== "running") return;
          setRoute("token"); // its progress is on the token tab
          setView("exporting");
          resume();
        });
      })
      .catch((e) => {
        if (answered || mine !== build.current) return;
        statusFailed(e);
      });
  }, [open, screens]);

  // On open, fill the name with what the board would be called anyway, so nothing arrives on
  // Miro untitled and the researcher sees the name before choosing it (owner, 17 Oct 2026).
  useEffect(() => {
    if (!open || named.current) return;
    apiGet<{ project_name: string }>("/info")
      .then((info) => {
        if (named.current) return;
        const name = info.project_name?.trim() ?? "";
        setBoardName(name && screens ? `${name} · ${t("screens.title")}` : name);
      })
      .catch(() => undefined);
  }, [open, screens, t]);

  // Closing the panel stops waiting on a build (the build itself goes on, and its chip-less
  // result is on the next status read); a reopened panel starts fresh.
  useEffect(() => {
    if (!open) {
      build.current += 1;
      opening.current += 1;
    }
  }, [open]);
  // Unmounting stops the wait too — a panel that is gone must not go on reading the build.
  useEffect(() => () => {
    build.current += 1;
  }, []);

  // Move focus into the dialog on open — the trigger is now inert (useInert),
  // so without this the keyboard/SR user is stranded on document.body behind
  // the inert wall.
  useEffect(() => {
    if (open) requestAnimationFrame(() => (headingRef.current ?? document.getElementById("bn-miro-title"))?.focus());
  }, [open]);

  // Announce async status transitions — the view swaps the subtitle text with
  // no live region, so a screen-reader user otherwise hears nothing.
  useEffect(() => {
    if (!open) return;
    if (view === "exporting") announce(t("miro.creatingBoard"));
    else if (view === "done")
      announce(t(screens ? "export.screens.done" : "miro.boardReady", { count: stickies }));
  }, [open, view, stickies, screens, t]);

  // Normalise through resolveBrowserLang for the same reason the HTML export
  // does: `i18n.language` can be a raw region tag (`en-GB`, `zh-TW`) that the
  // server's SUPPORTED_LOCALES check rejects, silently falling the board back
  // to English — the exact failure this send exists to end.
  const request = useCallback(
    (): MiroExportRequest => ({
      board_name: boardName.trim() || null,
      colour_by: colourBy,
      clips_base: featureFlags.boardClipLinks && linkClips ? clipsBase.trim() : "",
      locale: resolveBrowserLang(i18n.language) ?? "en",
      split_long_quotes: splitLong,
      sticky_shape: shape,
    }),
    [boardName, colourBy, linkClips, clipsBase, splitLong, shape, i18n.language],
  );

  // The Miro app route's board file: the FigJam export's own request, with the two choices the
  // in-Miro app honours. The board is named after the project (an empty name), and has no clip
  // links (parked: `featureFlags.boardClipLinks`).
  const fileRequest = useCallback(
    (): FigJamBoardRequest => ({
      board_name: "",
      locale: resolveBrowserLang(i18n.language) ?? "en",
      split_long_quotes: splitLong,
      sticky_shape: shape,
      clips_base: "",
    }),
    [splitLong, shape, i18n.language],
  );

  const choices = `${splitLong}|${shape}|${i18n.language}`;
  const copied = copiedFor === choices;
  const downloaded = downloadedFor?.choices === choices ? downloadedFor.quotes : null;

  const boardFileFailed = useCallback(
    (e: unknown) => {
      const reason = (e as ApiError | null)?.reason ?? "";
      setFileError(t(BOARD_FILE_ERROR_KEYS[reason] ?? "figjam.error"));
    },
    [t],
  );

  // Called synchronously in the click, or Safari refuses the clipboard write (boardClipboard.ts).
  const handleCopyBoard = () => {
    setFileError(null);
    setDownloadedFor(null);
    setFileBusy(true);
    const madeUnder = choices;
    const mine = opening.current;
    const live = () => mine === opening.current;
    let fetchFailed = false;
    copyBoardToClipboard(() =>
      // The whole board file at runtime; typed as the summary its other caller reads.
      (getFigJamBoard(fileRequest()) as unknown as Promise<BoardFile>).catch((e: unknown) => {
        fetchFailed = true;
        throw e;
      }),
    )
      .then(() => {
        if (!live()) return;
        setCopiedFor(madeUnder);
        announce(t("miro.copied"));
      })
      .catch((e: unknown) => {
        if (!live()) return;
        if (fetchFailed) boardFileFailed(e);
        else setFileError(t("miro.copyFailed"));
      })
      .finally(() => {
        if (live()) setFileBusy(false);
      });
  };

  // The FigJam panel's download: build it once to read its count and catch a refusal in words,
  // then hand the browser (or the Mac's save panel) the file's address.
  const handleDownloadBoard = async () => {
    setFileError(null);
    setCopiedFor(null);
    setFileBusy(true);
    const madeUnder = choices;
    const mine = opening.current;
    const live = () => mine === opening.current;
    const req = fileRequest();
    try {
      const summary = await getFigJamBoard(req);
      if (!live()) return; // closed while it was made: no download nobody is waiting for
      const a = document.createElement("a");
      a.href = figjamBoardDownloadUrl(req);
      a.download = "";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      setDownloadedFor({ choices: madeUnder, quotes: summary.totals.quotes });
      announce(t("figjam.downloading", { count: summary.totals.quotes }));
    } catch (e) {
      if (live()) boardFileFailed(e);
    } finally {
      if (live()) setFileBusy(false);
    }
  };

  /** The round "?" at the leading end of an action row: this route's help page. */
  const helpButton = (
    <a
      className="bn-help-btn"
      href={HELP_URL[tab]}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={t("nav.help")}
      title={t("nav.help")}
      data-testid="bn-miro-help"
    >
      ?
    </a>
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
        // In the browser the server's store is the only one, so say where the token couldn't be
        // saved. Not in the Mac app: there Python's Keychain write is a sandboxed no-op by design,
        // the durable copy goes through the bridge above, and the native sheet owns the warning.
        // Spoken through announce(), like the panel's other notices: a live region that mounts
        // with its text already in it is often not read out. (The panel itself is portalled
        // outside the inert app root, so its role="alert" errors do speak.)
        const warning =
          !isDesktop() && s.persisted === false && s.store ? t(PERSIST_WARNING_KEY[s.store]) : null;
        setPersistWarning(warning);
        if (warning) announce(warning);
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
      setPersistWarning(null);
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
    const mine = ++build.current;
    const live = () => mine === build.current;
    setBuildState(null);
    setSkipped(0);
    try {
      if (screens) {
        const { board_name, colour_by, locale, split_long_quotes, sticky_shape } = request();
        const start = await startScreensMiro({ board_name, colour_by, locale, split_long_quotes, sticky_shape });
        if (!live()) return;
        if (start.total === 0) {
          // Nothing to build: never read the status, which would be the last build's.
          setError(t("export.screens.none"));
          setView("configure");
          return;
        }
      } else {
        await startMiroBoard(request());
        if (!live()) return;
      }
    } catch (e) {
      if (!live()) return;
      // A refusal is a status, never the server's English: a reason the server named (not
      // connected, R94), else a build already running, or none.
      const reason = (e as { reason?: unknown } | null)?.reason;
      const named = typeof reason === "string" ? EXPORT_ERROR_KEYS[reason] : undefined;
      const msg = e instanceof Error ? e.message : "";
      // A 409 on the quotes board is the last one still stopping (Stop answers at once; the server
      // finishes the call in hand, which can be Miro's half-minute of refusing a new board).
      setError(t(named ?? (/ 409\b/.test(msg) ? (screens ? "export.screens.inProgress" : "miro.stillStopping")
        : screens && / 404\b/.test(msg) ? "export.screens.none" : "miro.exportError")));
      setView("configure");
      return;
    }
    await watch(mine);
  }, [request, screens, t, watch]);

  // Notice naming the destination workspace, with the team picked out (matches
  // the macOS sheet). Split the RAW template on the {{team}} placeholder (no
  // interpolation) so the <strong> lands on the slot regardless of the team's
  // text — a team literally named "board"/"new" can't mis-split. Same approach as
  // MiroSheet.swift's range(of: "{{team}}"); no <Trans> (keeps the bundle under
  // the size gate). The placeholder slot positions the emphasis per locale order.
  const renderNotice = () => {
    const upload = t(screens ? "miro.screensUploadNotice" : "miro.uploadNotice");
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

  return (
    <Dialog
      open={open}
      onClose={onClose}
      className="bn-board-modal"
      testId="bn-miro-overlay"
      modalTestId="bn-miro-modal"
      labelledBy="bn-miro-title"
    >
        {/* If the content crashes, the mark takes the heading's id and so names the dialog. */}
        <PanelErrorBoundary part labelId="bn-miro-title">
          {() => (
            <>
              <h2 id="bn-miro-title" ref={headingRef} tabIndex={-1}>
                {t(screens ? "miro.title" : "miro.quotesTitle")}
              </h2>

              {!screens && (
                <SegmentedTabs
                  tabs={[
                    { key: "app", label: t("miro.tabApp") },
                    { key: "token", label: t("miro.tabToken") },
                  ]}
                  selected={route}
                  onSelect={setRoute}
                  labelledBy="bn-miro-title"
                  idPrefix="bn-miro"
                />
              )}

              {tab === "app" && (
                <div role="tabpanel" id="bn-miro-panel-app" aria-labelledby="bn-miro-tab-app">
                  {/* The choices first, so they are made before anything leaves Bristlenose. */}
                  <label className="bn-export-checkbox">
                    <input
                      type="checkbox"
                      checked={splitLong}
                      onChange={(e) => setSplitLong(e.target.checked)}
                      data-testid="bn-miro-app-split-long"
                    />
                    <span>{t("miro.splitLongQuotes")}</span>
                  </label>
                  <fieldset className="bn-export-radios" data-testid="bn-miro-app-shape">
                    <legend className="bn-export-hint">{t("miro.stickyShape")}</legend>
                    {(["rectangle", "square"] as const).map((s) => (
                      <label key={s} className="bn-export-checkbox">
                        <input
                          type="radio"
                          name="bn-miro-app-shape"
                          value={s}
                          checked={shape === s}
                          onChange={() => setShape(s)}
                        />
                        <span>{t(s === "square" ? "miro.stickyShapeSquare" : "miro.stickyShapeRectangle")}</span>
                      </label>
                    ))}
                  </fieldset>
                  <hr />
                  <div className="bn-board-steps">
                    <p>
                      {withSlots(t("miro.appStep1"), {
                        link: (
                          <a href={MIRO_APP_INSTALL_URL} target="_blank" rel="noopener noreferrer">
                            {t("miro.appAddLink")}
                          </a>
                        ),
                      })}
                    </p>
                    <p className="bn-board-either">
                      {withSlots(t("miro.appEitherOr"), {
                        download: (
                          <button
                            type="button"
                            className="bn-btn bn-btn-secondary"
                            onClick={() => void handleDownloadBoard()}
                            disabled={fileBusy}
                            data-testid="bn-miro-download-board"
                          >
                            {t("figjam.download")}
                          </button>
                        ),
                        copy: (
                          <button
                            type="button"
                            className="bn-btn bn-btn-primary bn-keep-width"
                            onClick={handleCopyBoard}
                            disabled={fileBusy}
                            data-testid="bn-miro-copy-board"
                          >
                            {/* Both labels, one showing: the button keeps the wider one's width. */}
                            <span aria-hidden={copied}>{t("miro.copyBoard")}</span>
                            <span aria-hidden={!copied}>{t("miro.copied")}</span>
                          </button>
                        ),
                      })}
                    </p>
                    <p>{t("miro.appStep3")}</p>
                  </div>
                  {downloaded !== null && (
                    <p className="bn-export-hint" data-testid="bn-miro-downloaded">
                      {t("figjam.downloading", { count: downloaded })}
                    </p>
                  )}
                  {fileError && (
                    <p className="bn-export-error" role="alert">
                      {fileError}
                    </p>
                  )}
                  <div className="bn-modal-actions">
                    {helpButton}
                    <button className="bn-btn bn-btn-secondary" onClick={onClose}>
                      {t("miro.done")}
                    </button>
                  </div>
                </div>
              )}

              {tab === "token" && (
              <div
                role={screens ? undefined : "tabpanel"}
                id={screens ? undefined : "bn-miro-panel-token"}
                aria-labelledby={screens ? undefined : "bn-miro-tab-token"}
              >
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
                    {!screens && helpButton}
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
                  {persistWarning && (
                    <p className="bn-export-hint">
                      {persistWarning}
                    </p>
                  )}
                  {account && <p className="bn-export-hint">{account}</p>}
                  <label className="bn-export-hint" htmlFor="bn-miro-board-name">
                    {t("miro.boardNameLabel")}
                  </label>
                  <input
                    id="bn-miro-board-name"
                    type="text"
                    value={boardName}
                    placeholder={t("miro.boardNamePlaceholder")}
                    onChange={(e) => {
                      named.current = true;
                      setBoardName(e.target.value);
                    }}
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
                      checked={splitLong}
                      onChange={(e) => setSplitLong(e.target.checked)}
                      data-testid="bn-miro-split-long"
                    />
                    <span>{t("miro.splitLongQuotes")}</span>
                  </label>
                  <fieldset className="bn-export-radios" data-testid="bn-miro-shape">
                    <legend className="bn-export-hint">{t("miro.stickyShape")}</legend>
                    {(["rectangle", "square"] as const).map((s) => (
                      <label key={s} className="bn-export-checkbox">
                        <input
                          type="radio"
                          name="bn-miro-shape"
                          value={s}
                          checked={shape === s}
                          onChange={() => setShape(s)}
                        />
                        <span>{t(s === "square" ? "miro.stickyShapeSquare" : "miro.stickyShapeRectangle")}</span>
                      </label>
                    ))}
                  </fieldset>
                  {/* Clip links are a quotes-board option: the screens board's quotes sit beside their
                      screengrab, and its stickies carry no link (docs/design-screens-export.md §6). */}
                  {!screens && featureFlags.boardClipLinks && (
                    <>
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
                    </>
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
                    {!screens && helpButton}
                    <button className="bn-btn bn-btn-primary" onClick={handleExport} disabled={busy}>
                      {t("miro.createBoard")}
                    </button>
                  </div>
                </>
              )}

              {view === "exporting" && (
                <>
                  <p className="bn-modal-subtitle" data-testid="bn-miro-build-line">
                    {buildLine(t, buildState)}
                  </p>
                  {/* No value while there is no honest fraction (screenshots being made, the board
                      opening): the browser's own indeterminate bar. */}
                  <progress
                    className="bn-export-progress"
                    max={1}
                    value={buildState?.fraction ?? undefined}
                    aria-label={t("miro.creatingBoard")}
                    data-testid="bn-miro-build-bar"
                  />
                  {/* The line is kept when empty, so the dialog does not grow when a time arrives. */}
                  <p className="bn-export-hint">
                    {etaLine(t, buildState?.eta_seconds) ? (
                      <span data-testid="bn-miro-build-eta">{etaLine(t, buildState?.eta_seconds)}</span>
                    ) : (
                      "\u00a0"
                    )}
                  </p>
                  <div className="bn-modal-actions">
                    <button
                      className="bn-btn bn-btn-secondary"
                      onClick={() => {
                        // Stopping is acknowledged at once; the server finishes the call in hand, and
                        // the board keeps what it has. If the stop did not land (the build had just
                        // finished, or the request failed), read the build again and say what it did.
                        const stopped = ++build.current;
                        setView("configure");
                        (screens ? cancelScreensMiro : cancelMiroBoard)().catch(() => {
                          if (stopped !== build.current) return; // closed, or a new build begun
                          setView("exporting");
                          void watch(++build.current);
                        });
                      }}
                    >
                      {t("miro.cancel")}
                    </button>
                  </div>
                </>
              )}

              {view === "done" && (
                <>
                  <p className="bn-modal-subtitle">
                    {t(screens ? "export.screens.done" : "miro.boardReady", { count: stickies })}
                  </p>
                  {screens && skipped > 0 && (
                    <p className="bn-export-hint">
                      {t("export.screens.partial", { written: stickies, total: stickies + skipped })}
                    </p>
                  )}
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
              )}
            </>
          )}
        </PanelErrorBoundary>
    </Dialog>
  );
}
