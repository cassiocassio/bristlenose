/**
 * SessionsTable — React island that replaces the Jinja2 sessions table.
 *
 * Reads `data-project-id` from its mount point, fetches session data from
 * the API, and renders the full sessions table with visual parity to the
 * existing static HTML report.
 *
 * Speaker names are editable inline: code-only PersonBadge + EditableText
 * + pencil icon. Every rename goes through `nameSpeaker` (utils/speakerNames),
 * which writes it and makes it undoable.
 *
 * CSS classes match the existing theme so styles apply without changes.
 */

import { Suspense, lazy, useCallback, useContext, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { EditableText } from "../components/EditableText";
import { ErrorNotice } from "../components/RouteError";
import { JourneyChain } from "../components/JourneyChain";
import { PersonBadge } from "../components/PersonBadge";
import { SectionHeading } from "../components/SectionHeading";
import { Sparkline } from "../components/Sparkline";
import { Thumbnail } from "../components/Thumbnail";
import {
  personPickerNameTaken,
  unknownLetter,
  type PersonPickerChoice,
  type PersonPickerRow,
  type PersonPickerSlot,
  type PickerRole,
} from "../utils/personPicker";
import type { SparklineItem } from "../components/Sparkline";
import { PlayerContext } from "../contexts/PlayerContext";
import { apiGet, getPeople, isSessionScopedCode } from "../utils/api";
import {
  PEOPLE_CHANGED_EVENT,
  type PeopleChangedDetail,
  type SpeakerNameState,
} from "../utils/peopleChanged";
import { nameSpeaker, speakerWritesSettled, swapSpeakers } from "../utils/speakerNames";
import {
  hasNativePersonPicker,
  knownPeopleOf,
  nameStateOf,
  openNativePicker,
  pickerRoleOf,
  refuseTakenName,
  slotOf,
  swapPartnerOf,
  stateAfter,
} from "../utils/speakerPicking";
import type { PersonData } from "../utils/api";
import { postProjectAction } from "../shims/bridge";
import { isEmbedded } from "../utils/embedded";
import { isExportMode } from "../utils/exportData";
import { formatDurationHuman, formatFinderDate, formatFinderFilename } from "../utils/format";
import type {
  SessionResponse,
  SessionsListResponse,
  SpeakerResponse,
  TapestryResponse,
  TapestrySession,
} from "../utils/types";
import { TAPESTRY_GUTTER, fitScale, loadTapestryView, saveTapestryView, zoomScale } from "../utils/tapestryScale";
import { screenInk } from "../utils/sceneInk";
import { TapestryPreview } from "../components/TapestryPreview";
import { mergeTapestry } from "../utils/tapestryMerge";
import { diagnosticsEnabled } from "../utils/diagnostics";
import type { TranscriptionQuality } from "../components/TranscriptionDiagnostics";
import { handoverClass, useLensRead } from "../hooks/useLensRead";

// The picker's code is loaded when someone first opens it: the grid is part of
// first paint, and the picker is needed only on a click. The browser loads the
// web picker; the Mac app loads only the bridge, to ask for its native one.
// The timeline slice: lazy, because this island is on the first-paint path and
// a slice is only drawn once a row is opened.
const SessionTapestry = lazy(() => import("../components/SessionTapestry"));
const TranscriptionDiagnostics = lazy(() => import("../components/TranscriptionDiagnostics"));
/** Scene strips arrive after the report: while serve says they are pending, poll /tapestry from
 *  5 s apart, backing off to 30 s, for a few hours (a 4K capture decodes at minutes per hour). */
const stripPollDelay = (attempt: number) => Math.min(30_000, 5_000 * 1.5 ** attempt);
const STRIP_POLL_LIMIT = 400;
import { TapestryPlaygroundToggle } from "../components/TapestryPlaygroundToggle";
import { Icon } from "../components/Icon";
// Dev-only (`serve --dev`): nudge the tapestry's type and padding along the existing ladders.
const TapestryPlayground = lazy(() =>
  import("../components/TapestryPlayground").then((m) => ({ default: m.TapestryPlayground })),
);
const IS_DEV =
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_DEV__ === true || location.port === "5173";

const ReanalyseSessionSheet = lazy(() =>
  import("../components/ReanalyseSessionSheet").then((m) => ({ default: m.ReanalyseSessionSheet })),
);
const PersonPickerPopover = lazy(() =>
  import("../components/PersonPicker").then((m) => ({ default: m.PersonPickerPopover })),
);


// ---------------------------------------------------------------------------
// Sentiment → Sparkline mapping
// ---------------------------------------------------------------------------

const SENTIMENT_ORDER = [
  "frustration",
  "confusion",
  "doubt",
  "surprise",
  "confidence",
  "delight",
  "satisfaction",
];

/**
 * Placeholder role word shown (muted/italic) when a speaker has no identified
 * name yet — "Moderator" / "Participant" / "Observer", keyed off the badge code
 * prefix (m/o/…) rather than the stored role string, which is more robust (the
 * m-code speaker's stored role is "researcher", never "moderator").
 */
function speakerRolePlaceholder(
  code: string,
  t: (key: string, options?: Record<string, unknown>) => string,
): string {
  // Two unknowns of a role in one session are lettered, mA? and mB?, and so
  // are their names: Moderator A, Moderator B (design-people.md §J8.9).
  const letter = unknownLetter(code);
  if (code.startsWith("m")) {
    return letter
      ? t("sessions.speakerPlaceholder.moderatorLettered", { letter })
      : t("sessions.speakerPlaceholder.moderator");
  }
  if (code.startsWith("o")) {
    return letter
      ? t("sessions.speakerPlaceholder.observerLettered", { letter })
      : t("sessions.speakerPlaceholder.observer");
  }
  return t("sessions.speakerPlaceholder.participant");
}

function sentimentToSparklineItems(
  counts: Record<string, number>,
): SparklineItem[] {
  return SENTIMENT_ORDER.map((sentiment) => ({
    key: sentiment,
    count: counts[sentiment] || 0,
    colour: `var(--bn-sentiment-${sentiment})`,
  }));
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ModeratorHeader({
  moderatorNames,
}: {
  moderatorNames: string[];
}) {
  const { t } = useTranslation();
  if (moderatorNames.length === 0) return null;
  const label = t("sessions.moderatedBy", { names: oxfordList(moderatorNames) });
  return <p className="bn-session-moderators">{label}</p>;
}

function ObserverHeader({
  observerNames,
}: {
  observerNames: string[];
}) {
  const { t } = useTranslation();
  if (observerNames.length === 0) return null;
  const label = t("sessions.observer", { count: observerNames.length, names: oxfordList(observerNames) });
  return <p className="bn-session-moderators">{label}</p>;
}

function FolderIcon() {
  return (
    <Icon name="folder" px={14} decorative className="bn-folder-icon" />
  );
}

function oxfordList(items: string[]): string {
  if (items.length <= 1) return items.join("");
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return items.slice(0, -1).join(", ") + ", and " + items[items.length - 1];
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export function SessionsTable({
  projectId,
  refreshKey = 0,
}: {
  projectId: string;
  /** Bumped by LastRunStore on pipeline completion → triggers refetch. */
  refreshKey?: number;
}) {
  const { t } = useTranslation();
  const [data, setData] = useState<SessionsListResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [peopleMap, setPeopleMap] = useState<Record<string, PersonData> | null>(null);
  // `${session_id}:${speaker_code}` — moderator codes repeat across sessions,
  // so a bare code opened the editor in every session that had an `m1`.
  const [editingKey, setEditingKey] = useState<string | null>(null);
  // `${session}:${code}` of the speaker whose web picker is open.
  const [pickerKey, setPickerKey] = useState<string | null>(null);

  // The timeline slice under each row (GET /tapestry). Absent → no disclosure.
  const [tapestry, setTapestry] = useState<Record<string, TapestrySession> | null>(null);
  // How Whisper heard each recording, under its timeline — only with diagnostics on.
  const [quality, setQuality] = useState<Record<string, TranscriptionQuality>>({});
  // Restored, so a visit to a transcript and Back shows the same page.
  const [openTapestries, setOpenTapestries] = useState<Set<string>>(
    () => new Set(loadTapestryView(projectId).open),
  );
  const [zoom, setZoom] = useState(() => loadTapestryView(projectId).zoom);
  const [tuning, setTuning] = useState(false);
  const scrollSaveTimer = useRef<number | undefined>(undefined);
  const pendingScrollSave = useRef<(() => void) | null>(null);
  // A save still waiting when the lens unmounts (a click into a transcript) is written now.
  useEffect(() => () => {
    window.clearTimeout(scrollSaveTimer.current);
    pendingScrollSave.current?.();
  }, []);
  useEffect(() => {
    saveTapestryView(projectId, { open: [...openTapestries], zoom });
  }, [projectId, openTapestries, zoom]);
  const [gridWidth, setGridWidth] = useState(0);
  const gridRef = useRef<HTMLDivElement>(null);
  // Sessions whose timeline should animate open on its next mount, and ones animating closed.
  const landing = useRef(new Set<string>());
  const folding = useRef(new Set<string>());
  const navigate = useNavigate();
  // Bumped after a moderator or observer write lands: a pick or a new person
  // can renumber identities (m2 → m1), which only the server knows.
  const [reloadKey, setReloadKey] = useState(0);
  // The session whose re-analyse sheet is open (§J7 R3).
  const [reanalysing, setReanalysing] = useState<string | null>(null);
  // The grid: read on open, again after a run (once more if that fails) and after a speaker
  // write. A superseded read never overwrites a newer one's answer, either way.
  const { reload: reloadSessions, handingOver } = useLensRead<SessionsListResponse>({
    read: () => apiGet<SessionsListResponse>("/sessions"),
    apply: (json) => {
      setData(json);
      setError(null);
    },
    // The wire string is for the console (the hook logs it); the lens says it in its own words (R86).
    onError: (err) => setError(err instanceof Error && err.message ? err.message : "read failed"),
    refreshKey,
    key: projectId,
    label: "Sessions read failed:",
  });
  const reloadAfterWrites = useCallback(() => {
    void Promise.resolve()
      .then(speakerWritesSettled)
      .then(() => {
        setReloadKey((k) => k + 1);
        reloadSessions();
      });
  }, [reloadSessions]);

  // The layers under the grid, read with it.
  useEffect(() => {

    // Degraded, not broken: /sessions already carries the server-resolved
    // display name, so a failure here costs the full-name tooltip and the
    // short_name preference — not the names themselves. That's why it warns
    // rather than toasting. But it must not stay silent: an empty catch made
    // a failed fetch render pixel-identically to a study whose speakers
    // simply have no names, and those want different reactions.
    // While serve is still computing the scene strips (a background job after the report is
    // readable), refetch every few seconds, bounded, so the stripes arrive without a reload.
    let stripPoll: ReturnType<typeof setTimeout> | undefined;
    let cancelled = false;
    const fetchTapestry = (attempt: number) => {
      apiGet<TapestryResponse>("/tapestry")
        .then((json) => {
          if (cancelled) return;
          // Built here, not in the updater: a bad body then lands in the catch below, not in render.
          const next = Object.fromEntries(json.sessions.map((ts) => [ts.session_id, ts]));
          // Every refetch — a session imported during a run, a speaker write, a strip poll —
          // keeps the layers that did not change, so an open quote popover survives it.
          setTapestry((prev) => mergeTapestry(prev, next));
          // The export has no server to finish the job, so it never polls its own embedded answer.
          if (json.strips_pending && !isExportMode() && attempt < STRIP_POLL_LIMIT) {
            stripPoll = setTimeout(() => fetchTapestry(attempt + 1), stripPollDelay(attempt));
          }
        })
        .catch((err) => console.warn("SessionsTable: /tapestry failed; no timelines", err));
    };
    fetchTapestry(0);

    if (diagnosticsEnabled()) {
      apiGet<{ sessions: Record<string, TranscriptionQuality> }>("/transcription-quality")
        .then((json) => { if (!cancelled) setQuality(json.sessions ?? {}); })
        .catch((err) => console.warn("SessionsTable: /transcription-quality failed", err));
    }

    getPeople()
      .then(setPeopleMap)
      .catch((err) =>
        console.warn(
          "SessionsTable: /people failed; names fall back to /sessions",
          err,
        ),
      );
    return () => {
      cancelled = true;
      clearTimeout(stripPoll);
    };
  }, [projectId, refreshKey, reloadKey]);

  // The open/close animation loads after first paint, once there are timelines to open, so a
  // click finds it in the module cache and starts before the opened slice is painted.
  const haveTimelines = tapestry !== null;
  useEffect(() => {
    if (haveTimelines) void import("../utils/tapestryMotion");
  }, [haveTimelines]);

  // The slices share one scale, fitted to the grid's width.
  useEffect(() => {
    const el = gridRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => setGridWidth(el.clientWidth));
    ro.observe(el);
    setGridWidth(el.clientWidth);
    return () => ro.disconnect();
  }, [data]);

  // The grid's own copy, read by the write paths below at call time, so an
  // undo entry records what the slot held at the moment of the act.
  const dataRef = useRef(data);
  useEffect(() => {
    dataRef.current = data;
  }, [data]);

  /** What a slot holds, as the grid knows it. A missing flag reads as
   *  confirmed, as the grid draws it. `code` is the slot's address
   *  (`slotOf`), which every write path below carries. */
  const slotState = useCallback((sessionId: string, code: string): SpeakerNameState | null => {
    const sess = dataRef.current?.sessions.find((s) => s.session_id === sessionId);
    const sp = sess?.speakers.find((x) => slotOf(x) === code);
    return sp ? nameStateOf(sp) : null;
  }, []);

  /** Draw a slot's state. A participant code is study-wide, so every session
   *  showing it changes. A moderator or observer slot points at a person: this
   *  slot takes the person and the flag, and every slot of that person takes
   *  the names (a spelling fix lands everywhere). The codes, which a pick can
   *  renumber, arrive with the reload once the write has landed. */
  const drawSlot = useCallback((sessionId: string, code: string, state: SpeakerNameState) => {
    const sessionScoped = isSessionScopedCode(code);
    // Only a change of person can renumber codes; a rename or a confirm cannot.
    const current = dataRef.current?.sessions
      .find((sess) => sess.session_id === sessionId)
      ?.speakers.find((sp) => slotOf(sp) === code);
    const currentKind = current?.speaker_code.startsWith("o") ? "observer" : "moderator";
    const repointed =
      sessionScoped &&
      ((current?.person || undefined) !== (state.person || undefined) ||
        (!!state.kind && state.kind !== currentKind));
    const named = (sp: SpeakerResponse) => ({
      ...sp,
      name: state.short_name || state.full_name || "",
      full_name: state.full_name ?? sp.full_name,
      short_name: state.short_name,
    });
    setData((prev) => {
      if (!prev) return prev;
      return {
        ...prev,
        sessions: prev.sessions.map((sess) => ({
          ...sess,
          speakers: sess.speakers.map((sp) => {
            const here = sess.session_id === sessionId && slotOf(sp) === code;
            if (!sessionScoped) {
              return slotOf(sp) === code ? { ...named(sp), name_confirmed: state.confirmed } : sp;
            }
            if (here) {
              return state.person
                ? { ...named(sp), person: state.person, name_confirmed: state.confirmed }
                : { ...sp, name: "", full_name: "", short_name: "", person: "", name_confirmed: false };
            }
            return state.person && sp.person === state.person ? named(sp) : sp;
          }),
        })),
      };
    });
    if (repointed) reloadAfterWrites();
    if (!sessionScoped) {
      setPeopleMap((prev) =>
        prev && prev[code]
          ? {
              ...prev,
              [code]: {
                ...prev[code],
                full_name: state.full_name ?? prev[code].full_name,
                short_name: state.short_name,
              },
            }
          : prev,
      );
    }
  }, [reloadAfterWrites]);

  /** Every way a name changes here — the inline editor, either picker — ends
   *  in one undoable write (docs/design-people.md §B10). */
  const renameSlot = useCallback(
    (sessionId: string, code: string, change: (before: SpeakerNameState) => SpeakerNameState) => {
      // An export has no server: suppress the visible half too, or the change
      // would show and then silently revert on reload.
      if (isExportMode()) return;
      const before = slotState(sessionId, code);
      if (!before) return;
      const after = change(before);
      drawSlot(sessionId, code, after);
      // A failed write has said why and put the slot back (nameSpeaker).
      void nameSpeaker({ sessionId, code, before, after }).catch(() => undefined);
    },
    [slotState, drawSlot],
  );

  // A swap, or its undo or redo, changed two slots: read them again.
  useEffect(() => {
    // Through reloadAfterWrites: a quick ⌘Z then ⌘⇧Z must read after both land.
    window.addEventListener("bn:speakers-written", reloadAfterWrites);
    return () => window.removeEventListener("bn:speakers-written", reloadAfterWrites);
  }, [reloadAfterWrites]);

  // Undo and redo redraw the slot they changed.
  useEffect(() => {
    const onChanged = (e: Event) => {
      const { sessionId, code, state } = (e as CustomEvent<PeopleChangedDetail>).detail;
      drawSlot(sessionId, code, state);
    };
    window.addEventListener(PEOPLE_CHANGED_EVENT, onChanged);
    return () => window.removeEventListener(PEOPLE_CHANGED_EVENT, onChanged);
  }, [drawSlot]);

  const refuseTaken = refuseTakenName;

  /** The rows a slot's picker offers, from the grid as it is now. */
  const rowsFor = useCallback((sessionId: string, code: string) => {
    const sess = dataRef.current?.sessions.find((s) => s.session_id === sessionId);
    const sp = sess?.speakers.find((x) => slotOf(x) === code);
    if (!sp) return null;
    const slot: PersonPickerSlot = {
      code: sp.speaker_code,
      role: pickerRoleOf(sp.speaker_code),
      name: sp.name || "",
      confirmed: !(sp.name && sp.name_confirmed === false),
      person: sp.person || undefined,
    };
    const byRole = knownPeopleOf(dataRef.current);
    // A name is taken by any moderator or observer, whichever role (§J8.11).
    return {
      slot,
      known: slot.role === "participant" ? byRole.participant : [...byRole.moderator, ...byRole.observer],
    };
  }, []);

  // The pencil: a spelling fix for whoever the slot is, everywhere they
  // appear. On an unknown moderator or observer there is nobody to fix, so it
  // is someone new (§J8, answer 2).
  const handleNameCommit = useCallback(
    (sessionId: string, speakerCode: string, newName: string) => {
      setEditingKey(null);
      const found = rowsFor(sessionId, speakerCode);
      if (found) {
        const clash = personPickerNameTaken(found.slot, found.known, newName);
        if (clash) {
          refuseTaken(clash);
          return;
        }
      }
      renameSlot(sessionId, speakerCode, (before) =>
        isSessionScopedCode(speakerCode) && !before.person
          ? {
              person: crypto.randomUUID(),
              create: true,
              full_name: newName,
              short_name: newName,
              confirmed: true,
            }
          : { ...before, short_name: newName, confirmed: true },
      );
    },
    [renameSlot, rowsFor, refuseTaken],
  );

  // A pick, a new person, a confirm or a clear, from either picker. What each
  // means is the shared rule (stateAfter); a participant's typed name goes the
  // pencil's way, which refuses a taken one.
  const applyPickerChoice = useCallback(
    (sessionId: string, speakerCode: string, choice: PersonPickerChoice) => {
      if (choice.kind === "name") {
        handleNameCommit(sessionId, speakerCode, choice.name);
        return;
      }
      if (choice.kind === "swap") {
        // Two slots change at once; the grid re-reads when it lands (and on
        // its undo), since only the server knows the codes they now show.
        void swapSpeakers(sessionId, speakerCode, choice.slot).catch(() => undefined);
        return;
      }
      renameSlot(sessionId, speakerCode, (before) => stateAfter(choice, before));
    },
    [renameSlot, handleNameCommit],
  );


  // Only when there is no table to show. A failed refetch (after a run, a speaker
  // write) keeps the table already drawn and says why in the console above: one
  // failed background read replaced a good table with this notice (R86 wave 6).
  if (error && !data) {
    return (
      <section className="bn-session-table">
        <ErrorNotice scope="lens" />
      </section>
    );
  }

  if (!data) {
    return (
      <section className="bn-session-table">
        <p style={{ opacity: 0.5, padding: "1rem" }}>{t("sessions.loading")}</p>
      </section>
    );
  }

  const { sessions, source_folder_uri } = data;

  // Pre-pipeline / no-sessions cases are server-failure-page territory,
  // not SPA territory — see docs/private/handoffs/generic-failure-surface.md.

  // In the macOS app the folder proxy reveals the interviews folder in Finder
  // (native `reveal-in-finder` project action — sandbox-safe). In the browser
  // there's no native bridge, so fall back to copying the path to the clipboard.
  const embedded = isEmbedded();

  // The people known for each role across the study — what a moderator's or
  // observer's picker offers (personPickerRows), and the header's names.
  const knownPeople = knownPeopleOf(data);
  const knownNames: Record<PickerRole, string[]> = {
    moderator: knownPeople.moderator.map((r) => r.name),
    participant: knownPeople.participant.map((r) => r.name),
    observer: knownPeople.observer.map((r) => r.name),
  };

  // The Mac app opens its native picker over the badge; the browser (and an app
  // without one) opens the web one in place.
  const openPicker = (sessionId: string, slot: PersonPickerSlot, anchor: HTMLElement) => {
    if (isExportMode()) return;
    if (embedded && hasNativePersonPicker()) {
      // Native answers as a menu action, handed back to this grid's rule.
      const sp = data.sessions
        .find((s) => s.session_id === sessionId)
        ?.speakers.find((x) => x.speaker_code === slot.code);
      if (!sp) return;
      openNativePicker(
        {
          sessionId,
          code: slot.code,
          slot,
          known: knownPeople[slot.role],
          knownByRole: knownPeople,
          swap: swapPartnerOf(
            data.sessions.find((s) => s.session_id === sessionId)?.speakers ?? [], sp,
          ),
          apply: (choice) => applyPickerChoice(sessionId, slotOf(sp), choice),
          refuse: refuseTaken,
        },
        anchor,
      );
    } else {
      // A second click on the badge closes it, as a menu button does.
      const key = `${sessionId}:${slot.code}`;
      setEditingKey(null);
      setPickerKey((open) => (open === key ? null : key));
    }
  };

  const activateFolder = () => {
    if (!source_folder_uri) return;
    if (embedded) {
      postProjectAction("reveal-in-finder", { uri: source_folder_uri });
    } else {
      navigator.clipboard.writeText(source_folder_uri);
    }
  };
  const folderActionTitle = embedded
    ? t("sessions.showInFinder")
    : t("sessions.copyFolderPath");
  const interviewsHeader = source_folder_uri ? (
    // Link-styled action; keyboard-accessible via role/tabIndex/onKeyDown.
    // eslint-disable-next-line jsx-a11y/anchor-is-valid
    <a
      className="bn-interviews-link"
      href="#"
      role="button"
      tabIndex={0}
      onClick={(e: React.MouseEvent) => {
        e.preventDefault();
        activateFolder();
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          activateFolder();
        }
      }}
      title={folderActionTitle}
    >
      <FolderIcon /> {t("sessions.interviews")}
    </a>
  ) : (
    t("sessions.interviews")
  );

  // ── Session tapestry: one scale for every open slice, so sessions compare by eye.
  const hasTapestry = tapestry !== null && sessions.some((sess) => tapestry[sess.session_id]);
  // Every row's duration, readable or not — known from ingest (a recording's probe, a
  // platform transcript's last cue), so the scale is fixed from the first second and an
  // open timeline does not shrink when a longer one arrives. 0 (not known) is left out.
  const durations = sessions.map((sess) => sess.duration_seconds || tapestry?.[sess.session_id]?.duration_seconds || 0);
  const fit = fitScale(durations, gridWidth || 1000);
  const sPerPx = zoomScale(fit, zoom);
  // One label ink for every timeline on the screen, so names do not alternate dark and white.
  // Not a hook: this runs after the loading and error returns above. A few hundred turns.
  const clipInk = screenInk(
    Object.values(tapestry ?? {}).flatMap((ts) => (ts.turns ?? []).flatMap((tn) => (tn.colour ? [tn.colour] : []))),
  );
  // Opening from a click animates (utils/tapestryMotion.ts); a timeline restored on return does not.
  const rowOf = (sid: string) =>
    gridRef.current?.querySelector<HTMLElement>(`.bn-sessions-row[data-session="${CSS.escape(sid)}"]`) ?? null;
  const toggleTapestry = (sid: string, all: boolean) => {
    if (!all) {
      if (folding.current.has(sid)) return;
      if (!openTapestries.has(sid)) {
        landing.current.add(sid);
      } else {
        // A close before the lazy slice mounted must not leave an animation pending for the
        // next mount (a restore on return would then animate).
        landing.current.delete(sid);
        const row = rowOf(sid);
        const slice = document.getElementById(`bn-tapestry-${sid}`);
        const svg = slice?.querySelector<SVGSVGElement>(".bn-tapestry-svg");
        if (row && slice && svg) {
          folding.current.add(sid);
          // The close is the researcher's now: saved before the animation, so leaving the lens
          // mid-fold (a click into a transcript) still comes back to it closed.
          saveTapestryView(projectId, { open: [...openTapestries].filter((x) => x !== sid) });
          const close = () =>
            setOpenTapestries((prev) => {
              const next = new Set(prev);
              next.delete(sid);
              return next;
            });
          // Loaded on first use: the grid is on first paint, the animation is not.
          void import("../utils/tapestryMotion")
            .then((m) => m.foldTapestry({ row, slice, svg }))
            .catch(() => undefined)
            .then(close)
            .finally(() => folding.current.delete(sid));
          return;
        }
      }
    }
    setOpenTapestries((prev) => {
      const open = !prev.has(sid);
      // Option-click opens every readable row; a row readable later arrives closed (§2).
      if (all) {
        return open
          ? new Set(sessions.filter((sess) => (sess.state ?? "readable") === "readable").map((sess) => sess.session_id))
          : new Set();
      }
      const next = new Set(prev);
      if (open) next.add(sid);
      else next.delete(sid);
      return next;
    });
  };
  const zoomControl = hasTapestry ? (
    <div className="bn-tp-zoom">
      <button type="button" className="bn-tp-zoom-btn" aria-label={t("sessions.tapestry.zoomOut")}
        title={t("sessions.tapestry.zoomOut")} disabled={zoom <= 0} onClick={() => setZoom((z) => Math.max(0, z - 20))}>
        <Icon name="zoomOut" decorative />
      </button>
      <input type="range" className="bn-tp-zoom-slider" min={0} max={100} value={zoom}
        aria-valuetext={zoom === 0 ? "1×" : `${(fit / sPerPx).toFixed(1)}×`}
        aria-label={t("sessions.tapestry.zoom")} onChange={(e) => setZoom(Number(e.target.value))}
        onDoubleClick={() => setZoom(0)} />
      <button type="button" className="bn-tp-zoom-btn" aria-label={t("sessions.tapestry.zoomIn")}
        title={t("sessions.tapestry.zoomIn")} disabled={zoom >= 100} onClick={() => setZoom((z) => Math.min(100, z + 20))}>
        <Icon name="zoomIn" decorative />
      </button>
      {IS_DEV && <TapestryPlaygroundToggle onToggle={() => setTuning((v) => !v)} />}
      {IS_DEV && tuning && (
        <Suspense fallback={null}>
          <TapestryPlayground onClose={() => setTuning(false)} />
        </Suspense>
      )}
    </div>
  ) : null;
  // Each timeline scrolls on its own; remember where (once scrolling settles), so Back restores it.
  const rememberScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const src = e.target as HTMLElement;
    if (!src.classList?.contains("bn-tapestry-scroll")) return;
    const sid = src.closest(".bn-tapestry")?.id.replace(/^bn-tapestry-/, "");
    if (!sid) return;
    window.clearTimeout(scrollSaveTimer.current);
    pendingScrollSave.current = () =>
      saveTapestryView(projectId, { scroll: { ...loadTapestryView(projectId).scroll, [sid]: src.scrollLeft } });
    scrollSaveTimer.current = window.setTimeout(() => {
      pendingScrollSave.current?.();
      pendingScrollSave.current = null;
    }, 150);
  };

  return (
    <section className={handoverClass(handingOver, "bn-session-table")}>
      {/* Zone title. Must be a direct child of this <section> for the
          flush-to-datum rule to reach it
          (`.center > main > section:first-of-type > .section-heading`).
          Reuses `nav.sessions` rather than minting `sessions.heading` — the
          word is identical and already reviewed in all 20 locales. */}
      <SectionHeading action={zoomControl}>{t("nav.sessions")}</SectionHeading>
      {/* From the grid's own speakers, not the payload's moderator_names:
          the payload is read once, so a rename left the line naming
          moderators the grid no longer shows. */}
      <ModeratorHeader moderatorNames={knownNames.moderator} />
      <ObserverHeader observerNames={knownNames.observer} />
      {/* CSS grid, not a <table>. The responsive behaviour needs column
          reordering and a two-cells-into-one-column merge, neither of which
          CSS can do to a table. Roles keep the table semantics for assistive
          tech. Sizing, breakpoints and the degradation ladder all live in
          theme/organisms/sessions-grid.css — this component renders every
          cell at every width and lets container queries decide what shows,
          so there is no width measurement in JS. */}
      <div className="bn-sessions-grid" role="table" ref={gridRef} onScrollCapture={rememberScroll}>
        <div className="bn-sessions-row bn-sessions-head" role="row">
          <div className="bn-sessions-cell bn-cell-id" role="columnheader">
            {t("sessions.colId")}
          </div>
          <div className="bn-sessions-cell bn-cell-thumb" role="columnheader" />
          <div className="bn-sessions-cell bn-cell-speakers" role="columnheader">
            {t("sessions.colSpeakers")}
          </div>
          {/* Double-cell: the header stacks to match what the cell holds. */}
          <div className="bn-sessions-cell bn-cell-start" role="columnheader">
            <span className="bn-sessions-h1">{t("sessions.colStart")}</span>
            <span className="bn-sessions-h2">{t("sessions.colJourney")}</span>
          </div>
          <div className="bn-sessions-cell bn-cell-sentiment" role="columnheader">
            {t("sessions.colSentiment")}
          </div>
          <div className="bn-sessions-cell bn-cell-duration" role="columnheader">
            {t("sessions.colDuration")}
          </div>
          <div className="bn-sessions-cell bn-cell-file" role="columnheader">
            {interviewsHeader}
          </div>
        </div>
        {sessions.flatMap((sess) => {
          const ts = tapestry?.[sess.session_id];
          const open = !!ts && openTapestries.has(sess.session_id);
          // A turn carries the transcript's raw tag (the slot). The tag is only a join key: what
          // the row shows — and whose first letter is the speaker's kind after a recode — is the
          // displayed code /sessions emits (design-people.md §J7: nothing outside the server
          // reads a raw tag).
          const speakerOf = (slot: string) =>
            sess.speakers.find((x) => (x.slot_code || x.speaker_code) === slot);
          const codeOf = (slot: string) => speakerOf(slot)?.speaker_code || slot;
          const nameOf = (slot: string) => speakerOf(slot)?.name || codeOf(slot);
          const isTeamTurn = (tn: TapestrySession["turns"][number]) =>
            typeof tn.team === "boolean" ? tn.team : /^[mo]/.test(codeOf(tn.speaker));
          return [
          <SessionRow
            key={sess.session_id}
            tapestryOpen={ts ? open : undefined}
            preview={ts && gridWidth > 0 ? (
              <TapestryPreview session={ts} width={gridWidth} isTeam={isTeamTurn}
                onToggle={(all, sec) => {
                  // Opening from the strip aims the timeline at the moment clicked: it opens
                  // scrolled with that moment in the middle (the browser clamps at either end).
                  if (!all && !openTapestries.has(sess.session_id)) {
                    const at = Math.max(0, Math.round(TAPESTRY_GUTTER + sec / sPerPx - gridWidth / 2));
                    saveTapestryView(projectId, { scroll: { ...loadTapestryView(projectId).scroll, [sess.session_id]: at } });
                  }
                  toggleTapestry(sess.session_id, all);
                }} />
            ) : undefined}
            onToggleTapestry={(all) => toggleTapestry(sess.session_id, all)}
            session={sess}
            peopleMap={peopleMap}
            editingKey={editingKey}
            onEditStart={(key) => {
              setPickerKey(null);
              setEditingKey(key);
            }}
            onCancelEdit={() => setEditingKey(null)}
            onNameCommit={handleNameCommit}
            pickerKey={pickerKey}
            knownPeople={knownPeople}
            onPickerOpen={openPicker}
            onPickerClose={() => setPickerKey(null)}
            onPickerChoose={applyPickerChoice}
            onReanalyse={() => setReanalysing(sess.session_id)}
          />,
          open && ts ? (
            <div key={`${sess.session_id}-tapestry`} className="bn-tapestry" role="row"
              id={`bn-tapestry-${sess.session_id}`}>
              <div role="cell" className="bn-tapestry-cell" aria-colspan={7}>
                <Suspense fallback={null}>
                  <SessionTapestry
                    session={ts}
                    sPerPx={sPerPx}
                    clipInk={clipInk}
                    onReady={(svg) => {
                      if (!landing.current.delete(sess.session_id)) return;
                      const row = rowOf(sess.session_id);
                      const slice = document.getElementById(`bn-tapestry-${sess.session_id}`);
                      if (row && slice) {
                        void import("../utils/tapestryMotion").then((m) =>
                          m.landTapestry({ row, slice, svg, preview: row.querySelector(".bn-tapestry-preview-svg") }));
                      }
                    }}
                    initialScrollLeft={loadTapestryView(projectId).scroll[sess.session_id] ?? 0}
                    nameOf={nameOf}
                    codeOf={codeOf}
                    onJump={(sec) =>
                      navigate({ pathname: `/report/sessions/${sess.session_id}`, hash: `#t-${Math.floor(sec)}` })
                    }
                  >
                    {quality[sess.session_id] && (
                      // Its own boundary: the records arrive on a separate fetch, and a lazy
                      // chunk loading late must not blank a timeline already on screen.
                      <Suspense fallback={null}>
                      <TranscriptionDiagnostics
                        record={quality[sess.session_id]}
                        durationSeconds={ts.duration_seconds}
                        sPerPx={sPerPx}
                        onJump={(sec) =>
                          navigate({ pathname: `/report/sessions/${sess.session_id}`, hash: `#t-${Math.floor(sec)}` })
                        }
                      />
                      </Suspense>
                    )}
                  </SessionTapestry>
                </Suspense>
              </div>
            </div>
          ) : null,
          ];
        })}
      </div>
      {reanalysing && (
        <Suspense fallback={null}>
          <ReanalyseSessionSheet
            sessionId={reanalysing}
            sessionLabel={`#${data.sessions.find((x) => x.session_id === reanalysing)?.session_number ?? ""}`}
            onClose={() => setReanalysing(null)}
            onPinned={reloadAfterWrites}
          />
        </Suspense>
      )}
    </section>
  );
}

/** First word of a name, for the narrow-width short-name rung. Splits on
 *  whitespace only — names with no space (many CJK and Korean names, and
 *  mononyms) are already as short as they get and pass through unchanged
 *  rather than being sliced by codepoint. */
function shortName(name: string): string {
  return name.split(/\s+/)[0] || name;
}

// What inside a session row handles its own click, so the row's click-to-open
// stands aside. [role="menu"] is the person picker, which renders inside the row.
const ROW_OWN_CLICK =
  'a, button, input, textarea, select, [contenteditable="true"], [role="menu"], [data-own-click]';

function SessionRow({
  session,
  peopleMap,
  editingKey,
  onEditStart,
  onCancelEdit,
  onNameCommit,
  pickerKey,
  knownPeople,
  onPickerOpen,
  onPickerClose,
  onPickerChoose,
  tapestryOpen,
  onToggleTapestry,
  preview,
  onReanalyse,
}: {
  /** The closed timeline strip, drawn under the row's cells (components/TapestryPreview.tsx). */
  preview?: React.ReactNode;
  /** Open the re-analyse sheet for this session (§J7 R3). */
  onReanalyse?: () => void;
  /** undefined = this session has no timeline; true/false = its disclosure state. */
  tapestryOpen?: boolean;
  /** `all` = Option-click: open or close every row, as in a Finder outline. */
  onToggleTapestry?: (all: boolean) => void;
  session: SessionResponse;
  peopleMap: Record<string, PersonData> | null;
  editingKey: string | null;
  onEditStart: (key: string) => void;
  onCancelEdit: () => void;
  onNameCommit: (sessionId: string, code: string, newName: string) => void;
  pickerKey: string | null;
  knownPeople: Record<PickerRole, PersonPickerRow[]>;
  onPickerOpen: (sessionId: string, slot: PersonPickerSlot, anchor: HTMLElement) => void;
  onPickerClose: () => void;
  onPickerChoose: (sessionId: string, code: string, choice: PersonPickerChoice) => void;
}) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const {
    session_id,
    session_number,
    session_date,
    duration_seconds,
    has_media,
    thumbnail_url,
    speakers,
    journey_labels,
    journey,
    sentiment_counts,
    source_files,
  } = session;
  // A first analysis delivers sessions one by one (docs/design-progressive-
  // lenses.md §2). A row that is not readable yet is not a destination: no
  // data-session (the grid's hover and pointer key off it), no link, no player.
  const readable = (session.state ?? "readable") === "readable";
  const processing = session.state === "processing";

  // Journey arrow chain (now uses JourneyChain primitive). Each label deep-links
  // into this session's transcript at that screen's first moment, reusing the
  // transcript page's existing #t-<seconds> hash-scroll + highlight.
  const hasJourney = journey_labels.length > 0;
  // In export mode the app uses hash routing, so intra-app links must be
  // #-prefixed (a plain "/report/..." href navigates the browser off the
  // file:// document). The timecode rides as a nested #t-<seconds> the
  // transcript page resolves; clicks navigate via a router-agnostic location
  // object so both the browser and hash routers land correctly.
  const sessionPath = `/report/sessions/${session_id}`;
  const journeyAnchor = (index: number): string => {
    const step = journey[index];
    return step ? `#t-${Math.floor(step.start_seconds)}` : "";
  };
  const journeyHref = (index: number): string =>
    (isExportMode() ? `#${sessionPath}` : sessionPath) + journeyAnchor(index);

  // Source file display — media files open the popout player via PlayerContext;
  // non-media files are plain text.
  const playerCtx = useContext(PlayerContext);
  // Clicking either the filename link or the thumbnail opens the popout player.
  const openPlayer =
    readable && has_media && playerCtx ? () => playerCtx.seekTo(session_id, 0) : undefined;
  const videoTitle =
    source_files.length > 0 ? formatFinderFilename(source_files[0].filename) : undefined;
  let sourceEl: React.ReactNode = "\u2014";
  if (source_files.length > 0) {
    const sf = source_files[0];
    const displayName = formatFinderFilename(sf.filename);
    const titleAttr =
      displayName !== sf.filename ? sf.filename : undefined;
    if (!readable) {
      // The one being worked on carries the shimmer, on its filename only.
      sourceEl = (
        <span
          title={titleAttr}
          className={processing ? "bn-thinking-shimmer" : undefined}
          data-testid={processing ? "bn-session-processing" : undefined}
        >
          {displayName}
        </span>
      );
    } else if (has_media && !isExportMode()) {
      // Offline (export) has no media server / popout player — render the
      // filename as plain text rather than a dead #t=0 link.
      sourceEl = (
        <a
          href={`#t=0`}
          className="timecode"
          data-participant={session_id}
          data-seconds={0}
          data-end-seconds={0}
          title={titleAttr}
          onClick={(e) => {
            if (!playerCtx) return;
            if (e.metaKey || e.ctrlKey || e.shiftKey) return;
            e.preventDefault();
            playerCtx.seekTo(session_id, 0);
          }}
        >
          {displayName}
        </a>
      );
    } else {
      sourceEl = (
        <span title={titleAttr}>{displayName}</span>
      );
    }
  }

  // A click anywhere on a readable row opens its transcript, as the hover wash
  // and pointer promise. Controls inside the row (links, buttons, the name
  // editor, the person picker, the thumbnail's player) keep their own click,
  // and a drag that selected text is a selection, not a click.
  const onRowClick = readable
    ? (e: React.MouseEvent<HTMLDivElement>) => {
        // A modifier-click is a new-tab gesture, which only the row's #N link can honour.
        if (e.metaKey || e.ctrlKey || e.shiftKey) return;
        const target = e.target as HTMLElement;
        const own = target.closest(ROW_OWN_CLICK);
        if (own && e.currentTarget.contains(own)) return;
        if (window.getSelection()?.toString()) return;
        navigate(sessionPath);
      }
    : undefined;

  return (
    // The row click is a pointer convenience; the keyboard route is the #N link.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/interactive-supports-focus
    <div
      className={`bn-sessions-row${tapestryOpen ? " bn-tapestry-open" : ""}`}
      data-session={readable ? session_id : undefined}
      aria-disabled={readable ? undefined : true}
      role="row"
      onClick={onRowClick}
    >
      <div className="bn-sessions-cell bn-cell-id bn-session-id" role="cell">
        {readable && tapestryOpen !== undefined && (
          <button
            type="button"
            className="bn-tapestry-toggle"
            aria-expanded={tapestryOpen}
            aria-controls={tapestryOpen ? `bn-tapestry-${session_id}` : undefined}
            aria-label={t("sessions.tapestry.toggle", { number: session_number })}
            onClick={(e) => {
              e.stopPropagation();
              onToggleTapestry?.(e.altKey);
            }}
          >
            <Icon name="disclose" px={12} decorative />
          </button>
        )}
        {readable ? (
          <a href={isExportMode() ? `#${sessionPath}` : sessionPath}>
            #{session_number}
          </a>
        ) : (
          <span>#{session_number}</span>
        )}
      </div>
      <div className="bn-sessions-cell bn-cell-thumb" role="cell"
        data-own-click={openPlayer ? true : undefined}>
        {readable && (
          <Thumbnail
            hasMedia={has_media}
            thumbnailUrl={thumbnail_url ?? undefined}
            onActivate={openPlayer}
            title={videoTitle}
          />
        )}
      </div>
      <div className="bn-sessions-cell bn-cell-speakers bn-session-speakers" role="cell">
        {speakers.map((sp) => {
          // /people has one entry per code, so for a moderator or observer it
          // holds whichever session's name came last: use this session's.
          const person = isSessionScopedCode(sp.speaker_code)
            ? undefined
            : peopleMap?.[sp.speaker_code];
          const editKey = `${session_id}:${sp.speaker_code}`;
          const displayName = person?.short_name || sp.name || "";
          const fullName = person?.full_name || "";
          const nameTitle =
            fullName && fullName !== displayName ? fullName : undefined;
          const isEditing = editingKey === editKey;
          // A name the pipeline found and no person has said yes to yet: one
          // dotted ring round the badge, the name in grey (person-badge.css).
          // An exported report draws every name plain (design-people.md).
          const proposed = !isExportMode() && !!displayName && sp.name_confirmed === false;
          const slot: PersonPickerSlot = {
            code: sp.speaker_code,
            role: pickerRoleOf(sp.speaker_code),
            name: displayName,
            confirmed: !proposed,
            person: sp.person || undefined,
          };
          const canPick = !isEditing && !isExportMode();
          const badge = (
            <PersonBadge
              code={sp.speaker_code}
              role={sp.role as "participant" | "moderator" | "observer"}
            />
          );

          return (
            <span key={sp.speaker_code} className="bn-session-speaker-entry bn-person-picker-anchor">
              {/* The badge is the picker's button: "who is this speaker?" */}
              {canPick ? (
                <button
                  type="button"
                  className={`bn-person-picker-trigger${proposed ? " bn-person-proposed" : ""}`}
                  aria-haspopup="menu"
                  aria-expanded={pickerKey === editKey}
                  aria-label={
                    proposed
                      ? t("sessions.picker.proposedName", {
                          code: sp.speaker_code,
                          name: displayName,
                          interpolation: { escapeValue: false },
                        })
                      : undefined
                  }
                  data-testid={`bn-picker-trigger-${sp.speaker_code}`}
                  onClick={(e) => onPickerOpen(session_id, slot, e.currentTarget)}
                >
                  {badge}
                </button>
              ) : (
                <span className={proposed ? "bn-person-proposed" : undefined}>{badge}</span>
              )}
              {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
              <span
                data-own-click={canPick || undefined}
                onClick={
                  canPick
                    ? (e) => {
                        const trigger = (e.currentTarget.parentElement as HTMLElement)
                          .querySelector<HTMLElement>(".bn-person-picker-trigger");
                        onPickerOpen(session_id, slot, trigger ?? e.currentTarget);
                      }
                    : undefined
                }
                title={nameTitle}
              >
                <EditableText
                  value={displayName}
                  originalValue={sp.name}
                  trigger="external"
                  isEditing={isEditing}
                  onCommit={(newName) => onNameCommit(session_id, slotOf(sp), newName)}
                  onCancel={() => onCancelEdit()}
                  className={`bn-speaker-editable-name bn-speaker-name-full${proposed ? " proposed" : ""}`}
                  placeholder={speakerRolePlaceholder(sp.speaker_code, t)}
                  placeholderClassName="unnamed"
                  data-testid={`bn-name-${sp.speaker_code}`}
                />
                {/* Short form for the narrow-width rung. Rendered always and
                    swapped by container query, so the ladder stays CSS-only —
                    no width measurement, and it works from file:// in an
                    exported report. Not editable: editing at that width shows
                    the full name via the pencil path.

                    NOT aria-hidden. It used to be, to stop the name being
                    announced twice — but that can't happen: the base rule is
                    `.bn-speaker-name-short { display: none }` and the ≤750px
                    rung hides `.bn-speaker-name-full`, so exactly one of the
                    two is in the tree at any width and `display: none` is
                    already doing the de-duplication. The aria-hidden meant no
                    speaker name at all reached assistive tech between 750px
                    and 480px. (≤480px, rung 3 hides both — still a gap, and it
                    needs a visually-hidden swap rather than a delete.) */}
                <span
                  className={`bn-speaker-name-short${displayName ? "" : " unnamed"}`}
                >
                  {displayName
                    ? shortName(displayName)
                    : speakerRolePlaceholder(sp.speaker_code, t)}
                </span>
              </span>
              {/* Not rendered in an exported report: the name edit can't
                  persist offline, so the control is removed rather than left
                  dead. export.css hides it too, but that copy is baked
                  per-project and can be stale — the render gate is the one
                  that travels with the SPA. */}
              {!isEditing && !isExportMode() && (
                <button
                  className="bn-name-pencil"
                  onClick={() => onEditStart(editKey)}
                  aria-label={t("sessions.editName", { code: sp.speaker_code })}
                  data-testid={`bn-name-pencil-${sp.speaker_code}`}
                >
                  <Icon name="edit" decorative />
                </button>
              )}
              {pickerKey === editKey && (
                <Suspense fallback={null}>
                  <PersonPickerPopover
                    slot={slot}
                    known={knownPeople[slot.role]}
                    knownByRole={knownPeople}
                    swap={swapPartnerOf(speakers, sp)}
                    t={t}
                    onChoose={(choice) => onPickerChoose(session_id, slotOf(sp), choice)}
                    onClose={onPickerClose}
                  />
                </Suspense>
              )}
            </span>
          );
        })}
        {session.needs_reanalysis && onReanalyse && !isExportMode() && (
          // A speaker here moved into or out of participant: the quotes are
          // from the wrong speaker until the session is analysed again (§J7 R3).
          <button
            type="button"
            className="toolbar-btn bn-reanalyse-session"
            title={t("sessions.reanalyse.why")}
            onClick={(e) => { e.stopPropagation(); onReanalyse(); }}
            data-testid={`bn-reanalyse-${session_id}`}
          >
            {t("sessions.reanalyse.button")}
          </button>
        )}
      </div>
      {/* Deliberately NOT .bn-session-meta — that class is only the old
          `min-width: 12rem` stopgap, and it lives in the templates layer,
          which loads after organisms and would therefore win over this
          cell's `min-width: 0`, reinstating the very rigidity the shrink
          pair exists to remove. The journey styling comes from
          .bn-session-journey, which JourneyChain applies itself. */}
      <div className="bn-sessions-cell bn-cell-start" role="cell">
        <div>{formatFinderDate(session_date, i18n.language)}</div>
        {hasJourney && (
          <JourneyChain
            labels={journey_labels}
            hrefForIndex={journeyHref}
            onIndexClick={(i) => navigate({ pathname: sessionPath, hash: journeyAnchor(i) })}
          />
        )}
      </div>
      <div className="bn-sessions-cell bn-cell-sentiment bn-session-sentiment" role="cell">
        <Sparkline items={sentimentToSparklineItems(sentiment_counts)} />
      </div>
      {/* Duration and the interview file are separate cells at every width.
          Below the switch a container query drops them into one column,
          stacked — so the merge is CSS, not a second markup path. */}
      <div className="bn-sessions-cell bn-cell-duration bn-session-duration" role="cell">
        {readable || duration_seconds > 0 ? formatDurationHuman(duration_seconds) : null}
      </div>
      <div className="bn-sessions-cell bn-cell-file" role="cell">{sourceEl}</div>
      {readable && preview}
    </div>
  );
}
