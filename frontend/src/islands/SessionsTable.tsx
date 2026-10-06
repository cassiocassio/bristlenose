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
  personPickerRows,
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
import { toast } from "../utils/toast";
import type { PersonData } from "../utils/api";
import { postPersonPicker, postProjectAction } from "../shims/bridge";
import { isEmbedded } from "../utils/embedded";
import { isExportMode } from "../utils/exportData";
import { formatDurationHuman, formatFinderDate, formatFinderFilename } from "../utils/format";
import type { SessionResponse, SessionsListResponse, SpeakerResponse } from "../utils/types";
import { refetchOverlayProps } from "../hooks/useRefetching";

// The picker's code is loaded when someone first opens it: the grid is part of
// first paint, and the picker is needed only on a click. The browser loads the
// web picker; the Mac app loads only the bridge, to ask for its native one.
const PersonPickerPopover = lazy(() =>
  import("../components/PersonPicker").then((m) => ({ default: m.PersonPickerPopover })),
);
const loadPickerBridge = () => import("../utils/personPickerBridge");

/** Whether the host draws its own picker. The Mac app says so by setting this
 *  flag in the web view; without it — the browser, or an app build from
 *  before the native picker — the web picker opens, so a click never sends a
 *  message nothing answers. */
function hasNativePersonPicker(): boolean {
  return (window as unknown as Record<string, unknown>).__BRISTLENOSE_NATIVE_PERSON_PICKER__ === true;
}

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

/** The picker's role for a speaker code (the code prefix is the role; the
 *  stored moderator role is "researcher", never "moderator"). */
function pickerRoleOf(code: string): PickerRole {
  if (code.startsWith("m")) return "moderator";
  if (code.startsWith("o")) return "observer";
  return "participant";
}

/** How a write addresses a speaker: the slot code (`m1`, this session's
 *  first moderator), not the identity code the badge shows (`m2`). A pick
 *  can renumber identities, so a display code is never an address
 *  (docs/design-people.md §H H9, Phase 1). */
function slotOf(sp: SpeakerResponse): string {
  return sp.slot_code ?? sp.speaker_code;
}

/** The people known for each role across the study, in first-seen order —
 *  what a picker offers (`personPickerRows`). A moderator or observer is one
 *  row per person; a participant per name. */
function knownPeopleOf(data: SessionsListResponse | null): Record<PickerRole, PersonPickerRow[]> {
  const known: Record<PickerRole, PersonPickerRow[]> = { moderator: [], participant: [], observer: [] };
  for (const sess of data?.sessions ?? []) {
    for (const sp of sess.speakers) {
      if (!sp.name) continue;
      const list = known[pickerRoleOf(sp.speaker_code)];
      const key = sp.person || `name:${sp.name}`;
      if (list.some((r) => (r.person || `name:${r.name}`) === key)) continue;
      list.push({
        name: sp.name,
        code: sp.speaker_code,
        person: sp.person || undefined,
        full_name: sp.full_name,
        short_name: sp.short_name,
      });
    }
  }
  return known;
}

/**
 * Placeholder role word shown (muted/italic) when a speaker has no identified
 * name yet — "Moderator" / "Participant" / "Observer", keyed off the badge code
 * prefix (m/o/…) rather than the stored role string, which is more robust (the
 * m-code speaker's stored role is "researcher", never "moderator").
 */
function speakerRolePlaceholder(code: string, t: (key: string) => string): string {
  if (code.startsWith("m")) return t("sessions.speakerPlaceholder.moderator");
  if (code.startsWith("o")) return t("sessions.speakerPlaceholder.observer");
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
    getPeople()
      .then(setPeopleMap)
      .catch((err) =>
        console.warn(
          "SessionsTable: /people failed; names fall back to /sessions",
          err,
        ),
      );
  }, [projectId, refreshKey, reloadKey]);

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
    if (!sp) return null;
    return {
      full_name: sp.full_name,
      short_name: sp.short_name ?? sp.name,
      confirmed: sp.name_confirmed !== false,
      ...(isSessionScopedCode(code) ? { person: sp.person || undefined } : {}),
    };
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
    const repointed = sessionScoped && (current?.person || undefined) !== (state.person || undefined);
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

  /** A name another person already goes by, refused aloud (§J8.11). */
  const refuseTaken = useCallback(
    (name: string) => toast(t("sessions.picker.nameTaken", { name }), 5000),
    [t],
  );

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
    return { slot, known: knownPeopleOf(dataRef.current)[slot.role] };
  }, []);

  // The pencil: a spelling fix for whoever the slot is, everywhere they
  // appear. On an unknown moderator or observer there is nobody to fix, so it
  // is someone new (§J8, answer 2).
  const handleNameCommit = useCallback(
    (sessionId: string, speakerCode: string, newName: string) => {
      setEditingKey(null);
      const found = rowsFor(sessionId, speakerCode);
      if (found) {
        const rows = personPickerRows(found.slot, found.known);
        const clash = personPickerNameTaken(found.slot, rows, newName);
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

  // A pick, a new person or a confirm from either picker (§J8, answer 2).
  // A pick writes the person's own names back unchanged; someone new gets a
  // client-made uuid, so a redo finds the same person.
  const applyPickerChoice = useCallback(
    (sessionId: string, speakerCode: string, choice: PersonPickerChoice) => {
      if (choice.kind === "confirm") {
        renameSlot(sessionId, speakerCode, (before) => ({ ...before, confirmed: true }));
      } else if (choice.kind === "name") {
        handleNameCommit(sessionId, speakerCode, choice.name);
      } else if (choice.kind === "person") {
        const { row } = choice;
        renameSlot(sessionId, speakerCode, () => ({
          person: row.person,
          full_name: row.full_name,
          short_name: row.short_name ?? row.name,
          confirmed: true,
        }));
      } else {
        renameSlot(sessionId, speakerCode, () => ({
          person: crypto.randomUUID(),
          create: true,
          full_name: choice.name,
          short_name: choice.name,
          confirmed: true,
        }));
      }
    },
    [renameSlot, handleNameCommit],
  );

  // The Mac app's native picker answers through the menu-action channel with
  // a name and which row it came from; resolvePersonPickerChoice decides what
  // it means by the web picker's own rules, against the grid as it is now.
  useEffect(() => {
    // The native picker carries the code its badge showed — the identity's —
    // so it is turned back into the slot's address against the grid as it is.
    const speakerFor = (sessionId: string, code: string) =>
      dataRef.current?.sessions
        .find((s) => s.session_id === sessionId)
        ?.speakers.find((x) => x.speaker_code === code);
    const slotFor = (sessionId: string, code: string) => {
      const sp = speakerFor(sessionId, code);
      return sp ? rowsFor(sessionId, slotOf(sp)) : null;
    };
    const handler = (e: Event) => {
      const { action, payload } = (e as CustomEvent<{ action: string; payload?: unknown }>).detail;
      if (action !== "personPickerChoose") return;
      void loadPickerBridge().then(({ resolvePersonPickerChoice }) => {
        const pick = resolvePersonPickerChoice(payload, slotFor);
        const sp = pick ? speakerFor(pick.sessionId, pick.code) : undefined;
        if (!pick || !sp) return;
        if ("taken" in pick) refuseTaken(pick.taken);
        else applyPickerChoice(pick.sessionId, slotOf(sp), pick.choice);
      });
    };
    window.addEventListener("bn:menu-action", handler);
    return () => window.removeEventListener("bn:menu-action", handler);
  }, [applyPickerChoice, rowsFor, refuseTaken]);

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
      const rect = anchor.getBoundingClientRect();
      const known = knownPeople[slot.role];
      void loadPickerBridge().then(({ buildPersonPickerMessage }) =>
        postPersonPicker(buildPersonPickerMessage(sessionId, slot, known, rect, t)),
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

  return (
    <section {...refetchOverlayProps(isRefetching, "bn-session-table")}>
      {/* Zone title. Must be a direct child of this <section> for the
          flush-to-datum rule to reach it
          (`.center > main > section:first-of-type > .section-heading`).
          Reuses `nav.sessions` rather than minting `sessions.heading` — the
          word is identical and already reviewed in all 20 locales. */}
      <SectionHeading>{t("nav.sessions")}</SectionHeading>
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
      <div className="bn-sessions-grid" role="table">
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
        {sessions.map((sess) => (
          <SessionRow
            key={sess.session_id}
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
          />
        ))}
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
}: {
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
    <div className="bn-sessions-row" data-session={session_id} role="row">
      <div className="bn-sessions-cell bn-cell-id bn-session-id" role="cell">
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
