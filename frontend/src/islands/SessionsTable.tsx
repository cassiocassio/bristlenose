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
import { nameSpeaker, speakerWritesSettled } from "../utils/speakerNames";
import {
  hasNativePersonPicker,
  knownPeopleOf,
  nameStateOf,
  openNativePicker,
  pickerRoleOf,
  refuseTakenName,
  slotOf,
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
import { fitScale, loadTapestryView, saveTapestryView, zoomScale } from "../utils/tapestryScale";
import { refetchOverlayProps } from "../hooks/useRefetching";

// The picker's code is loaded when someone first opens it: the grid is part of
// first paint, and the picker is needed only on a click. The browser loads the
// web picker; the Mac app loads only the bridge, to ask for its native one.
// The timeline slice: lazy, because this island is on the first-paint path and
// a slice is only drawn once a row is opened.
const SessionTapestry = lazy(() => import("../components/SessionTapestry"));

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
    <svg
      className="bn-folder-icon"
      width="14"
      height="12"
      viewBox="0 0 14 12"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.3"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M1.5 2.5a1 1 0 0 1 1-1h2.6l1.4 1.5h5a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-9a1 1 0 0 1-1-1z" />
    </svg>
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

  const [isRefetching, setIsRefetching] = useState(false);
  // The timeline slice under each row (GET /tapestry). Absent → no disclosure.
  const [tapestry, setTapestry] = useState<Record<string, TapestrySession> | null>(null);
  // Restored, so a visit to a transcript and Back shows the same page.
  const [openTapestries, setOpenTapestries] = useState<Set<string>>(
    () => new Set(loadTapestryView(projectId).open),
  );
  const [zoom, setZoom] = useState(() => loadTapestryView(projectId).zoom);
  useEffect(() => {
    saveTapestryView(projectId, { open: [...openTapestries], zoom });
  }, [projectId, openTapestries, zoom]);
  const [gridWidth, setGridWidth] = useState(0);
  const gridRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  // Bumped after a moderator or observer write lands: a pick or a new person
  // can renumber identities (m2 → m1), which only the server knows.
  const [reloadKey, setReloadKey] = useState(0);
  const reloadAfterWrites = useCallback(() => {
    void Promise.resolve()
      .then(speakerWritesSettled)
      .then(() => setReloadKey((k) => k + 1));
  }, []);

  useEffect(() => {
    // refreshKey starts at 0; LastRunStore bumps it to 1 on the first
    // observed terminus. So a non-zero value is by definition a refetch
    // — no separate "is this the initial mount?" tracking needed.
    if (refreshKey > 0) setIsRefetching(true);
    apiGet<SessionsListResponse>("/sessions")
      .then((json) => setData(json))
      .catch((err: Error) => setError(err.message))
      .finally(() => setIsRefetching(false));

    // Degraded, not broken: /sessions already carries the server-resolved
    // display name, so a failure here costs the full-name tooltip and the
    // short_name preference — not the names themselves. That's why it warns
    // rather than toasting. But it must not stay silent: an empty catch made
    // a failed fetch render pixel-identically to a study whose speakers
    // simply have no names, and those want different reactions.
    apiGet<TapestryResponse>("/tapestry")
      .then((json) =>
        setTapestry(Object.fromEntries(json.sessions.map((ts) => [ts.session_id, ts]))),
      )
      .catch((err) => console.warn("SessionsTable: /tapestry failed; no timelines", err));

    getPeople()
      .then(setPeopleMap)
      .catch((err) =>
        console.warn(
          "SessionsTable: /people failed; names fall back to /sessions",
          err,
        ),
      );
  }, [projectId, refreshKey, reloadKey]);

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
      void nameSpeaker({ sessionId, code, before, after });
    },
    [slotState, drawSlot],
  );

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
      renameSlot(sessionId, speakerCode, (before) => stateAfter(choice, before));
    },
    [renameSlot, handleNameCommit],
  );


  if (error) {
    return (
      <section className="bn-session-table">
        <p style={{ color: "var(--bn-colour-danger, #c00)", padding: "1rem" }}>
          {t("sessions.failedToLoad", { error })}
        </p>
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
  const longest = Math.max(1, ...sessions.map((sess) => tapestry?.[sess.session_id]?.duration_seconds ?? 0));
  const sPerPx = zoomScale(fitScale(longest, gridWidth || 1000), zoom);
  const toggleTapestry = (sid: string, all: boolean) =>
    setOpenTapestries((prev) => {
      const open = !prev.has(sid);
      if (all) return open ? new Set(sessions.map((sess) => sess.session_id)) : new Set();
      const next = new Set(prev);
      if (open) next.add(sid);
      else next.delete(sid);
      return next;
    });
  const zoomControl = hasTapestry ? (
    <div className="bn-tp-zoom" role="group" aria-label={t("sessions.tapestry.zoom")}>
      <button type="button" className="bn-tp-zoom-btn" aria-label={t("sessions.tapestry.zoomOut")}
        title={t("sessions.tapestry.zoomOut")} onClick={() => setZoom((z) => Math.max(0, z - 20))}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="6.5" cy="6.5" r="4.5" /><path d="M10 10l3.5 3.5M4.5 6.5h4" /></svg>
      </button>
      <input type="range" className="bn-tp-zoom-slider" min={0} max={100} value={zoom}
        aria-valuetext={zoom === 0 ? "1×" : `${(fitScale(longest, gridWidth || 1000) / sPerPx).toFixed(1)}×`}
        aria-label={t("sessions.tapestry.zoom")} onChange={(e) => setZoom(Number(e.target.value))}
        onDoubleClick={() => setZoom(0)} />
      <button type="button" className="bn-tp-zoom-btn" aria-label={t("sessions.tapestry.zoomIn")}
        title={t("sessions.tapestry.zoomIn")} onClick={() => setZoom((z) => Math.min(100, z + 20))}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="6.5" cy="6.5" r="4.5" /><path d="M10 10l3.5 3.5M4.5 6.5h4M6.5 4.5v4" /></svg>
      </button>
    </div>
  ) : null;
  // Open slices scroll together: the axis is shared.
  const syncScroll = (e: React.UIEvent<HTMLDivElement>) => {
    const src = e.target as HTMLElement;
    if (!src.classList?.contains("bn-tapestry-scroll")) return;
    gridRef.current?.querySelectorAll<HTMLElement>(".bn-tapestry-scroll").forEach((el) => {
      if (el !== src && el.scrollLeft !== src.scrollLeft) el.scrollLeft = src.scrollLeft;
    });
    saveTapestryView(projectId, { scrollLeft: src.scrollLeft });
  };

  return (
    <section {...refetchOverlayProps(isRefetching, "bn-session-table")}>
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
      <div className="bn-sessions-grid" role="table" ref={gridRef} onScrollCapture={syncScroll}>
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
          const nameOf = (slot: string) => {
            // Unnamed: the identity code the row shows (m2, m?), not the transcript's slot token.
            const sp = sess.speakers.find((x) => (x.slot_code || x.speaker_code) === slot);
            return sp?.name || sp?.speaker_code || slot;
          };
          return [
          <SessionRow
            key={sess.session_id}
            tapestryOpen={ts ? open : undefined}
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
          />,
          open && ts ? (
            <div key={`${sess.session_id}-tapestry`} className="bn-tapestry" role="row"
              id={`bn-tapestry-${sess.session_id}`}>
              <div role="cell" className="bn-tapestry-cell" aria-colspan={7}>
                <Suspense fallback={null}>
                  <SessionTapestry
                    session={ts}
                    sPerPx={sPerPx}
                    initialScrollLeft={loadTapestryView(projectId).scrollLeft}
                    nameOf={nameOf}
                    onJump={(sec) =>
                      navigate({ pathname: `/report/sessions/${sess.session_id}`, hash: `#t-${Math.floor(sec)}` })
                    }
                  />
                </Suspense>
              </div>
            </div>
          ) : null,
          ];
        })}
      </div>
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
}: {
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
    has_media && playerCtx ? () => playerCtx.seekTo(session_id, 0) : undefined;
  const videoTitle =
    source_files.length > 0 ? formatFinderFilename(source_files[0].filename) : undefined;
  let sourceEl: React.ReactNode = "\u2014";
  if (source_files.length > 0) {
    const sf = source_files[0];
    const displayName = formatFinderFilename(sf.filename);
    const titleAttr =
      displayName !== sf.filename ? sf.filename : undefined;
    if (has_media && !isExportMode()) {
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

  return (
    <div
      className={`bn-sessions-row${tapestryOpen ? " bn-tapestry-open" : ""}`}
      data-session={session_id}
      role="row"
    >
      <div className="bn-sessions-cell bn-cell-id bn-session-id" role="cell">
        {tapestryOpen !== undefined && (
          <button
            type="button"
            className="bn-tapestry-toggle"
            aria-expanded={tapestryOpen}
            aria-controls={`bn-tapestry-${session_id}`}
            aria-label={t("sessions.tapestry.toggle", { number: session_number })}
            onClick={(e) => {
              e.stopPropagation();
              onToggleTapestry?.(e.altKey);
            }}
          >
            <svg width="9" height="9" viewBox="0 0 10 10" aria-hidden="true">
              <path d="M3 1.5 L7 5 L3 8.5" />
            </svg>
          </button>
        )}
        <a href={isExportMode() ? `#${sessionPath}` : sessionPath}>
          #{session_number}
        </a>
      </div>
      <div className="bn-sessions-cell bn-cell-thumb" role="cell">
        <Thumbnail
          hasMedia={has_media}
          thumbnailUrl={thumbnail_url ?? undefined}
          onActivate={openPlayer}
          title={videoTitle}
        />
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
                  &#x270E;
                </button>
              )}
              {pickerKey === editKey && (
                <Suspense fallback={null}>
                  <PersonPickerPopover
                    slot={slot}
                    known={knownPeople[slot.role]}
                    knownByRole={knownPeople}
                    t={t}
                    onChoose={(choice) => onPickerChoose(session_id, slotOf(sp), choice)}
                    onClose={onPickerClose}
                  />
                </Suspense>
              )}
            </span>
          );
        })}
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
        {formatDurationHuman(duration_seconds)}
      </div>
      <div className="bn-sessions-cell bn-cell-file" role="cell">{sourceEl}</div>
    </div>
  );
}
