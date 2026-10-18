/**
 * Discussion lens — the researcher's line of enquiry as planned and as asked,
 * with every participant's answers under the question that drew them.
 *
 * Shipped for beta 3 Oct 2026 (docs/design-discussion-lens-plan.md). It reads the
 * project's record through loadDiscussion() — codes from /discussion, names from
 * /sessions; quote cards are read-only (star, hide and tag arrive with QuoteGroup
 * once quotes have store ids).
 *
 * Interaction (decided 3 Oct 2026): focus is sticky and click-driven — a
 * navigator row or a question locks focus until clicked again or Esc; nothing
 * reacts to the pointer passing over. Normalised questions | Your guide switches
 * the navigator; with no guide the second tab is "Add your guide". The guide is a
 * left panel fitted by the shared rule (guidePanel.ts), not cut at a breakpoint.
 * Focus is shown by the shipped active and selection styles, never by dimming
 * the rest: opacity drops readable text below AA (review, 3 Oct 2026).
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";
import { Badge } from "../../components/Badge";
import { MicroBar } from "../../components/MicroBar";
import { PersonBadge } from "../../components/PersonBadge";
import { SectionHeading } from "../../components/SectionHeading";
import { announce } from "../../utils/announce";
import { isExportMode } from "../../utils/exportData";
import { dt } from "../../utils/platformTranslation";
import { formatDurationHuman, formatFinderFilename } from "../../utils/format";
import { isEmbedded } from "../../utils/embedded";
import { postProjectAction } from "../../shims/bridge";
import { CONTENT_FLOOR_PX, fitPanels } from "../../contexts/SidebarStore";
import { MIN_WIDTH, RESIZE_STEP } from "./split";
import { reportDiscussionGuide, useDiscussionGuide } from "./guidePanel";
import {
  ALL,
  barShare,
  capNames,
  cellQuotes,
  itemAnswers,
  litTurns,
  measureTier,
  mergedEntries,
  navEntries,
  sessionColumn,
  sessionForFocus,
  sessionLeftovers,
  sessionStats,
  shadeStep,
  wirePath,
  yieldThirds,
  type Focus,
  type GuideView,
  type Mode,
  type NavEntry,
  type NavRow,
  type Tier,
  type WireEnd,
} from "./model";
import { loadDiscussion, type DiscussionLoad } from "./loadDiscussion";
import { readLensState, writeLensState } from "./lensState";
import type { DiscussionData, DiscussionQuote, DiscussionSession, DiscussionTurn } from "./types";
import "./discussion.css";
import { discussionArrival } from "./discussionLinks";
import { appQuery } from "../../utils/appQuery";
import { markArrived } from "../../utils/arrival";

// The lens's strings, from `common.discussion.*`. Getters read the active
// language when called. RULE: every component that reads `S` must call
// useTranslation(), or it will not re-render on a language change — nothing
// else flags it (frontend/CLAUDE.md: i18n.t outside hooks).
const d = (key: string, vars?: Record<string, unknown>) => i18n.t(`discussion.${key}`, vars);
// Copy that tells the researcher what to DO forks by platform (dt): the CLI
// re-runs `bristlenose run`, which resumes and re-runs only this stage; on the
// Mac the only re-run is Re-analyse, which starts over and discards edits — so
// the Mac copy never sends anyone there (review, 3 Oct 2026).
const tAny = ((k: string) => i18n.t(k)) as unknown as TFunction;
const p = (key: string) => dt(tAny, `discussion.${key}`);
const S = {
  get title() { return d("title"); },
  get show() { return d("show"); },
  get planned() { return d("planned"); },
  get merged() { return d("merged"); },
  get plannedTip() { return d("plannedTip"); },
  get mergedTip() { return d("mergedTip"); },
  get guideView() { return d("guideView"); },
  get summary() { return d("summary"); },
  get original() { return d("original"); },
  get sessions() { return d("sessions"); },
  get navigator() { return d("navigator"); },
  get instruction() { return d("instruction"); },
  get standalone() { return d("standalone"); },
  session: (n: number) => d("session", { n }),
  stats: (duration: string, q: number, n: number) =>
    d("stats", { duration, questions: d("questionCount", { count: q }), quotes: d("quoteCount", { count: n }) }),
  get noAnswers() { return d("noAnswers"); },
  get all() { return d("all"); },
  get allSessions() { return d("allSessions"); },
  get notAskedIn() { return d("notAskedIn"); },
  get notAsked() { return d("notAsked"); },
  showSession: (n: number) => d("showSession", { n }),
  quotes: (n: number) => d("quoteCount", { count: n }),
  askedInOf: (asked: number, total: number, quotes: number) =>
    d("askedInOf", { asked, total, quotes: d("quoteCount", { count: quotes }) }),
  get keyMeasure() { return d("keyMeasure"); },
  get before() { return d("before"); },
  get noQuestions() { return d("noQuestions"); },
  get noSessions() { return d("noSessions"); },
  get unclassified() { return d("unclassified"); },
  others: (first: string, n: number) => d("others", { first, count: n }),
  sessionLabel: (n: number, names: string) => d("sessionLabel", { n, names }),
  get resize() { return d("resize"); },
  resizeText: (pct: number) => d("resizeText", { pct }),
  get loading() { return d("loading"); },
  get failed() { return d("failed"); },
  get markPlanned() { return d("markPlanned"); },
  get markBoth() { return d("markBoth"); },
  get markHollow() { return d("markHollow"); },
  get markPlus() { return d("markPlus"); },
  // Hover meanings for the marks — the house "? cursor + title" pattern
  // (Signals' metric labels and intensity dots).
  get addGuide() { return d("addGuide"); },
  get addGuideTab() { return d("addGuideTab"); },
  get addGuideHeading() { return d("addGuideHeading"); },
  get addGuideIntro() { return d("addGuideIntro"); },
  get addGuideFormats() { return d("addGuideFormats"); },
  get readingGuide() { return d("readingGuide"); },
  get chooseOtherGuide() { return d("chooseOtherGuide"); },
  get replaceGuide() { return d("replaceGuide"); },
  get guideHowTo() { return p("guideHowTo"); },
  get key() { return d("key"); },
  get keyBoth() { return d("keyBoth"); },
  get keyHollow() { return d("keyHollow"); },
  get keyPlus() { return d("keyPlus"); },
  get keyGrey() { return d("keyGrey"); },
  get tipPlanned() { return d("tipPlanned"); },
  get tipBoth() { return d("tipBoth"); },
  get tipHollow() { return d("tipHollow"); },
  get tipPlus() { return d("tipPlus"); },
  notHere: (n: number) => d("notHere", { n }),
  announceSession: (n: number, q: number) =>
    d("announceSession", { n, questions: d("questionCount", { count: q }) }),
  announceFocus: (text: string) => d("announceFocus", { text }),
  get announceClear() { return d("announceClear"); },
  get notRun() { return p("notRun"); },
  get stale() { return p("stale"); },
  get notBuilt() { return p("notBuilt"); },
  get exportNone() { return d("exportNone"); },
  get unmoderated() { return d("unmoderated"); },
  get allUnreliable() { return d("allUnreliable"); },
  guideProblem: (code: string) => p(`guideProblem.${code}`),
  sessionState: (state: string) => d(`sessionState.${state}`),
};

/** Intl.ListFormat is ES2021; the app's `lib` is ES2020, and every browser and
 *  WebKit we ship to has it — so reach it through a narrow local type. */
interface ListFormatter {
  format(list: string[]): string;
}
type ListFormatCtor = new (locale: string, opts: { style: string; type: string }) => ListFormatter;
const ListFormat = (Intl as unknown as { ListFormat?: ListFormatCtor }).ListFormat;

const NAV_MAX_SHARE = 0.6;   // the navigator may widen to 60% of the lens
// Its opening width: the CSS default it replaced, clamp(--bn-sidebar-width, 30vw, --bn-sidebar-max).
const NAV_OPEN_MIN = 280, NAV_OPEN_MAX = 480, NAV_OPEN_SHARE = 0.3;

interface Wire {
  d: string;
  stub: boolean;
  a: string;
  b: string;
  y1: number;
}

/** True when a dialog owns the keyboard: the app root goes inert under a modal. */
function modalOpen(target: EventTarget | null): boolean {
  if (document.getElementById("bn-app-root")?.hasAttribute("inert")) return true;
  return target instanceof Element && !!target.closest('[aria-modal="true"], [role="dialog"]');
}

/** Arrow keys move and select within a radio group (roving tabindex). */
function onRadioKeys<T extends string>(e: React.KeyboardEvent, values: T[], current: T, pick: (v: T) => void) {
  const i = values.indexOf(current);
  const next =
    e.key === "ArrowRight" || e.key === "ArrowDown" ? values[(i + 1) % values.length]
      : e.key === "ArrowLeft" || e.key === "ArrowUp" ? values[(i - 1 + values.length) % values.length]
        : e.key === "Home" ? values[0]
          : e.key === "End" ? values[values.length - 1]
            : null;
  if (next === null) return;
  e.preventDefault();
  pick(next);
  // the handler sits on the radio that has focus; its group is the parent
  const group = (e.currentTarget as HTMLElement).parentElement;
  requestAnimationFrame(() =>
    group?.querySelector<HTMLElement>(`[role="radio"][data-value="${CSS.escape(next)}"]`)?.focus(),
  );
}

/** Why a record has nothing to show. "Re-analyse to try again" only where a
 *  re-run can help: an unmoderated study (solo think-aloud) has no questions at
 *  all, and re-running cannot change that. */
function failedReason(data: DiscussionData | null): string {
  const states = data?.sessions.map((s) => s.state) ?? [];
  if (states.length && states.every((s) => s === "no_moderator")) return S.unmoderated;
  if (states.length && states.every((s) => s === "no_moderator" || s === "moderator_unreliable")) {
    return S.allUnreliable;
  }
  return S.notBuilt;
}

export function DiscussionLens() {
  useTranslation();
  const [load, setLoad] = useState<DiscussionLoad | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    loadDiscussion().then(
      (l) => live && setLoad(l),
      (e: unknown) => {
        // A 401, a 500 and an unknown record version all read the same on
        // screen, so the cause has to reach the console.
        console.error("discussion: load failed", e);
        if (live) setFailed(true);
      },
    );
    return () => {
      live = false;
    };
  }, []);
  // Every state carries a titled zone, as Signals' do, so the lens opens at the
  // same height loading, failed or empty as it does with data (lens template).
  const shell = (body: React.ReactNode) => (
    <section>
      <SectionHeading>{S.title}</SectionHeading>
      {body}
    </section>
  );
  if (failed) return shell(<p className="bn-empty-state" role="alert">{S.failed}</p>);
  if (!load) return shell(<p className="bn-empty-state" aria-busy="true">{S.loading}</p>);
  // Each state says what it is and what to do; none reads as "no questions".
  // An exported report's reader cannot re-run anything, so it gets one plain line.
  const none = (researcher: string) =>
    shell(<p className="bn-empty-state">{isExportMode() ? S.exportNone : researcher}</p>);
  if (load.status === "stale") return none(S.stale);
  if (load.status === "failed") return none(failedReason(load.data));
  const data = load.data;
  if (!data) return none(S.notRun);
  if (!data.sessions.length) return shell(<p className="bn-empty-state">{S.noSessions}</p>);
  return <DiscussionView data={data} />;
}

export function DiscussionView({ data }: { data: DiscussionData }) {
  const { i18n: tr } = useTranslation();
  const order = useMemo(() => data.sessions.map((s) => s.id), [data]);
  const saved = useMemo(() => readLensState(), []);
  // Arriving from a link (the transcript's gutter: docs/design-transcript-gutter.md): the address
  // names a guide item and the turn that asked it, and the lens opens on that asking, in that
  // turn's session, whatever it last showed. Read from the address, not the router: the lens's
  // tests mount it without one, and an export's hash router keeps the query in the hash.
  const arrived = useMemo(() => {
    const want = discussionArrival(appQuery());
    if (!want) return null;
    const turn = data.turns.find((tt) => tt.id === want.turn);
    if (turn && order.includes(turn.session)) return { item: want.item, turn: turn.id as string | null, session: turn.session as string | null };
    // The turn has gone (the record was rebuilt, or the address is old): the item, if it is still
    // in the guide, is the next best place to land.
    console.warn("Discussion: the turn asked for is not in this record", want.turn);
    const known = data.sections.some((sec) => sec.items.some((it) => it.id === want.item))
      || data.standalone.some((it) => it.id === want.item);
    return known ? { item: want.item, turn: null, session: null } : null;
  }, [data, order]);
  const [mode, setMode] = useState<Mode>(data.guide ? saved.mode : "merged");
  const [guideView, setGuideView] = useState<GuideView>(saved.guideView);
  const [guideNote, setGuideNote] = useState(false);
  // All is the first choice and the default once there are two sessions (decided 17 Oct 2026);
  // with one, All would be that session twice, so there is no All.
  const multi = order.length > 1;
  const [session, setSession] = useState<string>(() => {
    if (arrived?.session) return arrived.session;
    if (saved.session === ALL && multi) return ALL;
    if (saved.session && order.includes(saved.session)) return saved.session;
    return multi ? ALL : (order[0] ?? "");
  });
  const all = session === ALL;
  const [focus, setFocus] = useState<Focus | null>(arrived ? { item: arrived.item, turn: arrived.turn } : saved.focus);
  const [navW, setNavW] = useState<number | null>(saved.navWidth);
  // The navigator's measure (bar + count → strip → grid), chosen by measuring the guide.
  const [tier, setTier] = useState<Tier>("bar");
  // Measured in the same frame as the wires — never read from the DOM during render.
  const [sizes, setSizes] = useState<{ lens: number; nav: number; gut: number; view: number }>(
    { lens: 1000, nav: MIN_WIDTH, gut: 40, view: 1000 });
  const guide = useDiscussionGuide();
  const [wires, setWires] = useState<Wire[]>([]);
  const [dragging, setDragging] = useState(false);
  const [splitHover, setSplitHover] = useState(false);

  useEffect(() => {
    if (!dragging) writeLensState({ mode, guideView, session, focus, navWidth: navW });
  }, [mode, guideView, session, focus, navW, dragging]);

  const lensRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const gutRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const probeRef = useRef<HTMLSpanElement>(null); // a one-digit head badge: the grid's pitch
  const lastWires = useRef("");

  // "Sarah and Mike", "Tom, Dick and Harry" — the UI locale's own list form.
  // Bristlenose's "en" is British English: en-GB has no serial comma.
  const list = useMemo<ListFormatter | null>(() => {
    if (!ListFormat) return null;
    // The language actually serving the strings ("en"), not the detected tag
    // ("en-US"), which would put an American serial comma into British copy.
    const lang = tr.resolvedLanguage || tr.language || "en";
    try {
      return new ListFormat(lang === "en" ? "en-GB" : lang, { style: "long", type: "conjunction" });
    } catch {
      return null;
    }
  }, [tr.resolvedLanguage, tr.language]);
  const join = useCallback((n: string[]) => (list ? list.format(n) : n.join(", ")), [list]);
  // Names arrive joined from /sessions (loadDiscussion), never in the discussion
  // payload, so an anonymised export shows codes (plan §9.C).
  const namesOf = useCallback((s: DiscussionSession) => capNames(s.participants, join, S.others), [join]);
  // An anonymised export blanks names: join only the ones there are, or a
  // session reads "#1  and " to a screen reader.
  const fullNames = useCallback(
    (s: DiscussionSession) => join(s.participants.map((p) => p.name).filter(Boolean)), [join]);
  const byId = useMemo(() => new Map(data.sessions.map((s) => [s.id, s])), [data]);
  const num = useCallback((sid: string) => byId.get(sid)?.number ?? 0, [byId]);

  const entries = useMemo(() => navEntries(data, mode, guideView), [data, mode, guideView]);
  const column = useMemo(() => sessionColumn(data, session), [data, session]);
  const stats = useMemo(() => sessionStats(data, session), [data, session]);
  const lit = useMemo(() => litTurns(data, session, focus), [data, session, focus]);
  const current = byId.get(session);
  // What each session gave each question — the All column and the measure count the same thing.
  const answers = useMemo(() => itemAnswers(data), [data]);
  const leftovers = useMemo(() => sessionLeftovers(data), [data]);
  // A session whose questions could not be classified never reads as "not asked" (types.ts).
  const readable = useMemo(
    () => new Set(data.sessions.filter((sess) => !sess.state || sess.state === "ok").map((sess) => sess.id)), [data]);
  const thirds = useMemo(() => {
    const counts: number[] = [];
    for (const bySession of answers.values()) {
      for (const asks of bySession.values()) counts.push(asks.reduce((n, a) => n + a.answers.length, 0));
    }
    return yieldThirds(counts);
  }, [answers]);
  const rowTotal = useCallback(
    (r: NavRow) => r.sessions.reduce((n, sid) => n + cellQuotes(answers, r.id, sid), 0), [answers]);
  const rowMax = useMemo(
    () => Math.max(0, ...entries.filter((x): x is NavRow => x.type === "row").map(rowTotal)), [entries, rowTotal]);

  // ── selection & focus ──
  const selectSession = useCallback(
    (sid: string) => {
      setSession(sid);
      // a question is per session; keep its topic, drop the specific ask
      setFocus((f) => (f && f.turn ? { item: f.item, turn: null } : f));
      announce(sid === ALL ? S.allSessions
        : S.announceSession(num(sid), data.turns.filter((t) => t.session === sid && t.item).length));
    },
    [data, num],
  );

  const focusRow = useCallback((row: NavRow) => {
    // A line never asked in any session has nothing to light: focusing it would
    // dim every wire and light nothing — a dead click. It does not take focus.
    if (!row.sessions.length) return;
    if (focus && focus.item === row.id && !focus.turn) {
      setFocus(null); // clearing never moves the reader to another session
      announce(S.announceClear);
      return;
    }
    setFocus({ item: row.id, turn: null });
    setSession((s) => sessionForFocus(s, row.sessions));
    announce(S.announceFocus(row.text));
  }, [focus]);

  const focusAsk = useCallback((turn: DiscussionTurn) => {
    if (focus && focus.turn === turn.id) {
      setFocus(null);
      announce(S.announceClear);
      return;
    }
    setFocus({ item: turn.item ?? "", turn: turn.id });
    announce(S.announceFocus(turn.text));
  }, [focus]);

  // View ▸ Next/Previous Question (the Mac menu, bn:menu-action): step the navigator's focus to
  // the next question that was asked, in the order the navigator lists them, wrapping. A step
  // always lands on a question (it never toggles focus off the way a second click does).
  useEffect(() => {
    const onMenu = (e: Event) => {
      const action = (e as CustomEvent<{ action?: string }>).detail?.action;
      if (action !== "nextQuestion" && action !== "previousQuestion") return;
      const rows = entries.filter((x): x is NavRow => x.type === "row" && x.sessions.length > 0);
      if (!rows.length) return;
      const at = focus ? rows.findIndex((r) => r.id === focus.item) : -1;
      const dir = action === "nextQuestion" ? 1 : -1;
      const next = rows[at < 0 ? (dir > 0 ? 0 : rows.length - 1) : (at + dir + rows.length) % rows.length];
      setFocus({ item: next.id, turn: null });
      setSession((sid) => sessionForFocus(sid, next.sessions));
      announce(S.announceFocus(next.text));
    };
    window.addEventListener("bn:menu-action", onMenu);
    return () => window.removeEventListener("bn:menu-action", onMenu);
  }, [entries, focus]);

  // Esc clears focus; 1–9 pick a session. Never claims a key someone else handled,
  // a key typed into a field, or one pressed while a dialog owns the keyboard.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey || modalOpen(e.target)) return;
      // the target can be the document itself, which has no closest()
      const t = e.target;
      if (t instanceof Element && t.closest("input, textarea, select, [contenteditable='true']")) return;
      if (e.key === "Escape" && focus) {
        setFocus(null);
        announce(S.announceClear);
        e.preventDefault();
        return;
      }
      const n = Number(e.key);
      if (Number.isInteger(n) && n >= 1 && n <= order.length) {
        selectSession(order[n - 1]);
        e.preventDefault();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [focus, order, selectSession]);

  // An arrival brings the asking it names into view, once, and flashes it (utils/arrival.ts).
  useEffect(() => {
    if (!arrived?.turn) return;
    const el = contentRef.current?.querySelector<HTMLElement>(`.dl-ask[data-turn="${arrived.turn.replace(/["\\]/g, "\\$&")}"]`);
    if (!el) return;
    if (typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "center" });
    markArrived(el);
  }, [arrived]);

  // Bring the first lit question into view when a navigator row takes focus.
  useEffect(() => {
    if (!focus || focus.turn) return;
    // In All the question has a heading of its own: land on it, not on its first session's ask.
    const el = session === ALL
      ? contentRef.current?.querySelector<HTMLElement>(`.dl-item[data-item="${CSS.escape(focus.item)}"]`)
      : contentRef.current?.querySelector<HTMLElement>(".dl-ask.hot");
    if (!el) return;
    const r = el.getBoundingClientRect();
    const barH = barRef.current?.getBoundingClientRect().height ?? 0;
    if (r.top < barH || r.bottom > window.innerHeight) el.scrollIntoView({ block: "start" });
  }, [focus, session]);

  // ── geometry: bar height, badge collapse, wires ──
  useLayoutEffect(() => {
    const bar = barRef.current, lens = lensRef.current;
    if (!bar || !lens || typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(() => lens.style.setProperty("--dl-bar-h", `${bar.getBoundingClientRect().height}px`));
    ro.observe(bar);
    return () => ro.disconnect();
  }, []);

  // The grid's pitch is a ONE-digit head badge plus 4px (decided 18 Oct 2026): a 10–12 head is
  // squeezed into the same box, so twelve sessions cost twelve one-digit columns, not two-digit
  // ones. The probe is always laid out (invisible), so the measure never reads a hidden element.
  const fitMeasure = useCallback(() => {
    const nav = navRef.current, lens = lensRef.current;
    const head = probeRef.current?.firstElementChild;
    if (!nav || !lens) return;
    const w = head ? head.getBoundingClientRect().width : 0;
    const pitch = Math.ceil(w) + 4;
    if (w > 0) {
      lens.style.setProperty("--dl-head-w", `${w}px`);
      lens.style.setProperty("--dl-pitch", `${pitch}px`);
    }
    const next = measureTier(nav.clientWidth, order.length, pitch);
    setTier((t) => (t === next ? t : next));
  }, [order.length]);

  const drawWires = useCallback(() => {
    const gut = gutRef.current, nav = navRef.current, content = contentRef.current;
    const out: Wire[] = [];
    // All reads in the guide's own order, so a wire would join a row to the heading beside it.
    const allView = lensRef.current?.dataset.all === "true";
    if (gut && nav && content && gut.offsetParent !== null && !allView) {
      const g = gut.getBoundingClientRect();
      const nb = nav.getBoundingClientRect();
      const end = (el: Element, top: number, bottom: number): WireEnd => {
        const b = el.getBoundingClientRect();
        const y = b.top + Math.min(b.height / 2, 11);
        return { y: y - g.top, off: y < top + 4 ? -1 : y > bottom - 6 ? 1 : 0 };
      };
      content.querySelectorAll<HTMLElement>(".dl-ask[data-item]").forEach((q) => {
        const item = q.dataset.item ?? "";
        if (!item) return; // an unclassified turn has no row to wire to
        const row = nav.querySelector(`.dl-row[data-id="${CSS.escape(item)}"]`);
        if (!row) return;
        const from = end(row, nb.top, nb.bottom);
        const p = wirePath(from, end(q.querySelector(".quote-row") ?? q, g.top, window.innerHeight), g.width);
        if (p) out.push({ ...p, a: item, b: q.dataset.turn ?? "", y1: from.y });
      });
    }
    // A frame that changed nothing must not re-render the lens.
    const key = out.map((w) => `${w.a}>${w.b}:${w.d}`).join("|");
    if (key === lastWires.current) return;
    lastWires.current = key;
    setWires(out);
  }, []);

  useEffect(() => {
    let raf = 0;
    const schedule = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        const lens = lensRef.current?.clientWidth ?? 0, nav = navRef.current?.getBoundingClientRect().width ?? 0;
        // The gutter measures 0 while the guide is folded: keep the last real width.
        const gutNow = gutRef.current?.getBoundingClientRect().width ?? 0, view = window.innerWidth;
        if (lens) setSizes((p) => {
          const gut = gutNow > 0 ? gutNow : p.gut;
          return p.lens === lens && p.nav === nav && p.gut === gut && p.view === view ? p : { lens, nav, gut, view };
        });
        fitMeasure();
        drawWires();
      });
    };
    schedule();
    const nav = navRef.current;
    window.addEventListener("scroll", schedule, { passive: true });
    window.addEventListener("resize", schedule);
    nav?.addEventListener("scroll", schedule, { passive: true });
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("scroll", schedule);
      window.removeEventListener("resize", schedule);
      nav?.removeEventListener("scroll", schedule);
    };
  }, [fitMeasure, drawWires, entries, column, navW, all]);

  // ── the split ──
  const navMax = Math.max(MIN_WIDTH, NAV_MAX_SHARE * sizes.lens);
  const clamp = (w: number) => Math.round(Math.min(navMax, Math.max(MIN_WIDTH, w)));
  // A width saved on a wider window is pulled back to this one's ceiling.
  const effectiveW = navW === null ? null : clamp(navW);

  // ── the guide as a left panel (guidePanel.ts) ──
  // The shared rule decides whether it shows: the conversation keeps its floor
  // beside the guide at its narrowest, and a guide opened by hand is never
  // folded for you. It narrows to its minimum before it folds.
  const preferredW = effectiveW ?? clamp(Math.min(NAV_OPEN_MAX, Math.max(NAV_OPEN_MIN, NAV_OPEN_SHARE * sizes.view)));
  const guideShown = fitPanels({
    tocWanted: guide.wish, tagsWanted: false, tocWidth: MIN_WIDTH + sizes.gut, tagsWidth: 0,
    rightColumn: false, available: sizes.lens, exempt: guide.justOpened ? "toc" : null,
  }).tocOpen;
  const navWidth = Math.max(MIN_WIDTH, Math.min(preferredW, sizes.lens - sizes.gut - CONTENT_FLOOR_PX));
  // What the Mac reads to fold the projects column before the guide narrows.
  const wantedWidth = Math.round((guide.wish ? preferredW + sizes.gut : 0) + CONTENT_FLOOR_PX);
  useEffect(() => reportDiscussionGuide(guideShown, wantedWidth), [guideShown, wantedWidth]);
  const onSplitDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (e.button !== 0) return;
    e.preventDefault();
    const handle = e.currentTarget;
    handle.setPointerCapture?.(e.pointerId);
    const startX = e.clientX;
    const startW = navRef.current?.getBoundingClientRect().width ?? MIN_WIDTH;
    setDragging(true);
    document.body.classList.add("dragging");
    const move = (ev: PointerEvent) => setNavW(clamp(startW + ev.clientX - startX));
    const end = () => {
      setDragging(false); // the width is persisted once, on release (see writeLensState)
      document.body.classList.remove("dragging");
      handle.removeEventListener("pointermove", move);
      handle.removeEventListener("pointerup", end);
      handle.removeEventListener("pointercancel", end);
    };
    handle.addEventListener("pointermove", move);
    handle.addEventListener("pointerup", end);
    handle.addEventListener("pointercancel", end);
  };
  const onSplitKey = (e: React.KeyboardEvent) => {
    const w = effectiveW ?? sizes.nav;
    const step: Record<string, number> = { ArrowLeft: -RESIZE_STEP, ArrowRight: RESIZE_STEP };
    if (e.key in step) setNavW(clamp(w + step[e.key]));
    else if (e.key === "Home") setNavW(MIN_WIDTH);
    else if (e.key === "End") setNavW(Math.round(navMax));
    else return;
    e.preventDefault();
  };

  // ── render ──
  const sessionBadge = (sid: string, label?: string) => (
    <span className={sid === session ? "bn-person-badge-here" : undefined}>
      <PersonBadge code={`#${num(sid)}`} role="participant" name={label} />
    </span>
  );

  const markTip = (r: NavRow) =>
    mode === "planned" ? S.tipPlanned
      : r.mark === "dot" ? S.tipBoth : r.mark === "hollow" ? S.tipHollow : S.tipPlus;

  const markText = (r: NavRow) =>
    mode === "planned" ? S.markPlanned
      : r.mark === "dot" ? S.markBoth : r.mark === "hollow" ? S.markHollow : S.markPlus;

  // The label a session's cell, head or lead-in reads by: "#3 Bettina and Kwame", or "#4".
  const sessionName = (sid: string) => {
    const sess = byId.get(sid);
    return sess ? S.sessionLabel(sess.number, fullNames(sess)).trim() : "";
  };

  // The row's measure, replacing the session chips and #N ▾ (decided 18 Oct 2026). One cell per
  // session, shaded by the quotes it drew in the study's thirds; not asked and asked-but-nothing
  // are drawn alike. Then the row's total as the tags sidebar's bar and count, the bar
  // logarithmic so one quote never looks like none. The tier (lens class) shows what fits.
  const measure = (r: NavRow) => {
    const total = rowTotal(r);
    return (
      <span className="dl-measure">
        <span className="dl-cells">
          {data.sessions.map((sess) => {
            const asked = r.sessions.includes(sess.id);
            const q = asked ? cellQuotes(answers, r.id, sess.id) : 0;
            const label = `${sessionName(sess.id)} · ${
              asked ? S.quotes(q) : readable.has(sess.id) ? S.notAsked : S.unclassified}`;
            return (
              // Not a tab stop: twelve per row would bury the guide. The keyboard reaches the
              // same place through the session bar (focus is kept) or the All view's lead-ins.
              <button key={sess.id} type="button" tabIndex={-1} title={label} aria-label={label}
                aria-disabled={asked ? undefined : true}
                className={`dl-cell s${shadeStep(q, thirds)}${sess.id === session ? " here" : ""}`}
                onClick={() => {
                  if (!asked) return;
                  selectSession(sess.id);
                  setFocus({ item: r.id, turn: null });
                }} />
            );
          })}
        </span>
        <span className="tag-bar-area">
          {total > 0 && <MicroBar value={barShare(total, rowMax)} colour="var(--dl-bar)" />}
          <span className="tag-count" aria-hidden="true">{total}</span>
        </span>
        <span className="bn-sr-only">{`, ${S.askedInOf(r.sessions.length, data.sessions.length, total)}`}</span>
      </span>
    );
  };

  const row = (r: NavRow) => {
    // In All every session is showing, so nothing is greyed for "not asked in this session".
    const asked = all || r.sessions.includes(session);
    const on = !!focus && focus.item === r.id;
    const cls = ["toc-link", "dl-row"];
    if (!r.sessions.length) cls.push("dim");
    else if (!asked) cls.push("ghost");
    if (r.mark === "hollow") cls.push("unasked");
    if (on) cls.push("active");
    return (
      <div key={r.id} className={cls.join(" ")} data-id={r.id}>
        <button type="button" className="dl-row-btn" title={r.title} onClick={() => focusRow(r)}
          aria-pressed={r.sessions.length ? on : undefined} aria-disabled={r.sessions.length ? undefined : true}>
          {data.guide ? (
            <span className="dl-mk" aria-hidden="true" title={markTip(r)}>
              {r.mark === "plus" ? "+" : <span className={r.mark === "hollow" ? "dl-dot hollow" : "dl-dot"} />}
            </span>
          ) : (
            // No guide uploaded: nothing can be said about planned or off-guide
            // (there almost certainly was a guide; it just isn't here). Only that
            // these are the questions asked, normalised: a faint dot holds the
            // column the marks use (4 Oct 2026).
            <span className="dl-mk dl-mid" aria-hidden="true">·</span>
          )}
          <span className="dl-tx">{r.text}</span>
          <span className="bn-sr-only">{`${data.guide ? `, ${markText(r)}` : ""}${asked || !r.sessions.length ? "" : S.notHere(num(session))}`}</span>
        </button>
        {measure(r)}
      </div>
    );
  };

  // Navigator sections: a heading, then its rows, as one labelled group.
  const sections = useMemo(() => {
    const out: { head: Extract<NavEntry, { type: "head" }>; rows: NavRow[] }[] = [];
    for (const e of entries) {
      if (e.type === "head") out.push({ head: e, rows: [] });
      else out[out.length - 1]?.rows.push(e);
    }
    return out;
  }, [entries]);

  const quoteCard = (q: DiscussionQuote, forTurn: string) => (
    <blockquote key={q.key} className={`quote-card${lit.has(forTurn) ? " hot" : ""}`} data-for={forTurn}>
      <div className="quote-row">
        <span className="timecode">[{q.time}]</span>
        <div className="quote-body">
          <span className="quote-text-wrapper">
            <span className="smart-quote">{"“"}</span>
            <span className="quote-text">{q.text}</span>
            <span className="smart-quote">{"”"}</span>
          </span>{" "}
          <span className="speaker">
            <PersonBadge code={q.participant} role="participant" name={q.name || undefined} />
          </span>
          {q.sentiment && (
            <div className="badges">
              <Badge text={q.sentiment} variant="ai" sentiment={q.sentiment} />
            </div>
          )}
        </div>
      </div>
    </blockquote>
  );

  const askRow = (t: DiscussionTurn, noAnswers: boolean) => (
    <blockquote key={t.id} className={`quote-card dl-ask${lit.has(t.id) ? " hot" : ""}`}
      data-item={t.item ?? ""} data-turn={t.id}>
      <div className="quote-row">
        <span className="timecode">[{t.time}]</span>
        <div className="quote-body">
          <button type="button" className="dl-ask-btn" aria-pressed={!!focus && focus.turn === t.id}
            onClick={() => focusAsk(t)}>
            <span className="moderator-question-text">{t.text}</span>
          </button>
          <span className="speaker">
            <PersonBadge code={t.speaker ?? "m1"} role="moderator" />
          </span>
          {t.kind === "unclassified" && <Badge text={S.unclassified} variant="readonly" />}
          {noAnswers && <span className="dl-noans">{S.noAnswers}</span>}
        </div>
      </div>
    </blockquote>
  );

  const hotWire = (a: string, b: string) =>
    !!focus && (focus.turn ? focus.turn === b : focus.item === a && lit.has(b));

  const style = { "--dl-nav-w": `${Math.round(navWidth)}px` } as React.CSSProperties;

  const chooseGuide = () => (isEmbedded() ? postProjectAction("choose-discussion-guide") : setGuideNote(true));
  // The house small secondary button, as at the foot of the Codebook navigator.
  const guideButton = (label: string) => (
    <button type="button" className="bn-btn bn-btn-secondary bn-btn-sm" onClick={chooseGuide}>{label}</button>
  );
  // With no guide, the second tab is only where one is added: no key, no rows.
  const adding = mode === "planned" && !data.guide;
  const shownSections = adding ? [] : sections;
  // Without a guide the marks say nothing, so the key keeps only its grey line.
  const keyMarks = new Set(data.guide ? shownSections.flatMap(({ rows }) => rows.map((r) => r.mark)) : []);
  // Normalised questions first: it is the view the lens opens on.
  const modes: Mode[] = ["merged", "planned"];
  // All: the guide's order, each question once, then one block per session that asked it —
  // the session's lead-in (its badge, which opens that session at this question), the
  // moderator's own wording, the quotes. Sessions that never asked it: one line at the foot.
  // All is built from the merged record whatever the navigator shows: Your guide lists only
  // the guide's own lines, and All must not lose the questions asked off it (review, 18 Oct).
  const allSections = useMemo(() => {
    const out: { head: Extract<NavEntry, { type: "head" }>; rows: NavRow[] }[] = [];
    for (const e of mergedEntries(data)) {
      if (e.type === "head") out.push({ head: e, rows: [] });
      else out[out.length - 1]?.rows.push(e);
    }
    return out.map((x) => ({ ...x, rows: x.rows.filter((r) => r.sessions.length > 0) }))
      .filter((x) => x.rows.length > 0);
  }, [data]);

  // A session's lead-in in All: its bar badge, a button that opens that session (at the question).
  const leadIn = (sess: DiscussionSession, item: string | null) => (
    <button type="button" className="dl-from" title={S.showSession(sess.number)}
      onClick={() => {
        selectSession(sess.id);
        if (item) setFocus({ item, turn: null });
      }}>
      <PersonBadge code={`#${sess.number}`} role="participant" name={namesOf(sess) || undefined} />
    </button>
  );

  // All: the guide's order, each question once, then one block per session that asked it —
  // the session's lead-in, the moderator's own wording, the quotes. Sessions that never asked
  // it: one line at the foot. Quotes before the first question open the column and asks the
  // model never classified close it, so every quote a session view shows is here too.
  const allColumn = () => {
    const seconds = data.sessions.reduce((n, sess) => n + (sess.seconds || 0), 0);
    // The same counts a session's own line gives, summed: asks, and every quote.
    const asks = data.turns.filter((t) => t.item).length;
    const withBefore = data.sessions.filter((sess) => leftovers.get(sess.id)?.before.length);
    const withUnclassified = data.sessions.filter((sess) => leftovers.get(sess.id)?.unclassified.length);
    return (
      <section>
        <SectionHeading>{S.allSessions}</SectionHeading>
        <div className="dl-meta">
          <span className="dl-stats">{S.stats(formatDurationHuman(seconds), asks, data.quotes.length)}</span>
        </div>
        {data.sessions.filter((sess) => !readable.has(sess.id)).map((sess) => (
          // A session that contributes nothing says why here too — never silently absent.
          <p key={sess.id} className="dl-before dl-state" role="note">
            <PersonBadge code={`#${sess.number}`} role="participant" compact /> {S.sessionState(sess.state!)}
          </p>
        ))}
        {withBefore.length > 0 && (
          <div className="dl-part-group">
            <h2 className="dl-part">{S.before}</h2>
            {withBefore.map((sess) => (
              <div key={sess.id} className="dl-group">
                {leadIn(sess, null)}
                {leftovers.get(sess.id)!.before.map((q) => quoteCard(q, ""))}
              </div>
            ))}
          </div>
        )}
        {allSections.map(({ head, rows }) => (
          <div key={head.id} className="dl-part-group">
            <h2 className="dl-part">{head.id === "standalone" ? S.standalone : head.title}</h2>
            {rows.map((r) => {
              const missing = data.sessions.filter((sess) => readable.has(sess.id) && !r.sessions.includes(sess.id));
              return (
                <div key={r.id} className="dl-item" data-item={r.id}>
                  <h3>{r.text}</h3>
                  {r.sessions.map((sid) => {
                    const sess = byId.get(sid);
                    if (!sess) return null;
                    return (
                      <div key={sid} className="dl-group">
                        {leadIn(sess, r.id)}
                        {(answers.get(r.id)?.get(sid) ?? []).map(({ turn, answers: said }) => [
                          askRow(turn, said.length === 0),
                          ...said.map((q) => quoteCard(q, turn.id)),
                        ])}
                      </div>
                    );
                  })}
                  {missing.length > 0 && (
                    <p className="dl-before dl-notasked">
                      <span>{S.notAskedIn}</span>
                      {missing.map((sess) => (
                        <PersonBadge key={sess.id} code={`#${sess.number}`} role="participant" compact absent />
                      ))}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        ))}
        {withUnclassified.length > 0 && (
          // Asks the model never classified: each carries its "not classified" badge (askRow).
          <div className="dl-part-group dl-leftovers">
            {withUnclassified.map((sess) => (
              <div key={sess.id} className="dl-group">
                {leadIn(sess, null)}
                {leftovers.get(sess.id)!.unclassified.map(({ turn, answers: said }) => [
                  askRow(turn, said.length === 0),
                  ...said.map((q) => quoteCard(q, turn.id)),
                ])}
              </div>
            ))}
          </div>
        )}
      </section>
    );
  };

  // The session bar's choices, in order: All (with two sessions or more), then each session.
  const picks = multi ? [ALL, ...order] : order;
  const showKey = keyMarks.size > 0 || !all || tier !== "bar";

  return (
    <div ref={lensRef} className={`dl-lens dl-m-${tier}${focus ? " has-focus" : ""}${guideShown ? "" : " guide-hidden"}`}
      style={style} data-testid="discussion-lens" data-all={all ? "true" : "false"}>
      <div ref={barRef} className="dl-bar">
        <div className="dl-bar-nav">
        {/* Always both tabs: with no guide, the second is where one is added. An
            export cannot add one, so there it is only shown when there is a guide. */}
        {data.guide || !isExportMode() ? (
          <span className="dimension-toggle" role="radiogroup" aria-label={S.show}>
            {modes.map((m) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} data-value={m}
                tabIndex={mode === m ? 0 : -1} onKeyDown={(e) => onRadioKeys(e, modes, mode, setMode)}
                title={m === "planned" ? (data.guide ? S.plannedTip : undefined) : S.mergedTip}
                className={`dimension-btn${mode === m ? " active" : ""}`} onClick={() => setMode(m)}>
                {m === "merged" ? S.merged : data.guide ? S.planned : S.addGuideTab}
              </button>
            ))}
          </span>
        ) : (
          <span />
        )}
        </div>
        <div className="dl-sessions" role="radiogroup" aria-label={S.sessions}>
          {multi && (
            // All, first, then a keyline: All is a different kind of choice from a session.
            <>
              <button type="button" role="radio" aria-checked={all} data-value={ALL}
                tabIndex={all ? 0 : -1} className="dl-sess"
                onKeyDown={(e) => onRadioKeys(e, picks, session, selectSession)}
                aria-label={S.allSessions} title={S.allSessions} onClick={() => selectSession(ALL)}>
                <span className={all ? "bn-person-badge-here" : undefined}>
                  <PersonBadge code={S.all} role="participant" />
                </span>
              </button>
              <span className="dl-sep" aria-hidden="true" />
            </>
          )}
          {data.sessions.map((s) => (
            <button key={s.id} type="button" role="radio" aria-checked={s.id === session} data-value={s.id}
              tabIndex={s.id === session ? 0 : -1} className="dl-sess"
              onKeyDown={(e) => onRadioKeys(e, picks, session, selectSession)}
              aria-label={S.sessionLabel(s.number, fullNames(s))} title={fullNames(s) ? `${S.session(s.number)}: ${fullNames(s)}` : S.session(s.number)}
              onClick={() => selectSession(s.id)}>
              {sessionBadge(s.id, namesOf(s))}
            </button>
          ))}
        </div>
      </div>

      <nav ref={navRef} id="dl-nav" className="dl-nav toc-sidebar-body" aria-label={S.navigator}>
        {mode === "planned" && guide.pendingGuide && (
          // The Mac has copied a guide in and a run is reading it. The report
          // reloads when the run ends — finished, failed or stopped — which
          // clears this (guidePanel.ts).
          <p className="dl-before dl-reading" role="status">
            {S.readingGuide} <span className="dl-reading-file">{formatFinderFilename(guide.pendingGuide, 32)}</span>
          </p>
        )}
        {mode === "planned" && data.guide && (
          // Native radios: arrow keys and announcement come with the element.
          <div className="dl-guide-view" role="radiogroup" aria-label={S.guideView}>
            <label>
              <input type="radio" name="dl-guide-view" value="summary" checked={guideView === "summary"}
                onChange={() => setGuideView("summary")} />
              {S.summary}
            </label>
            {data.guide_file ? (
              // The original is shown by its file name, which is also how you
              // choose a different guide (4 Oct 2026). The radio and the link are
              // separate controls: nothing interactive nests inside a label.
              <span className="dl-guide-opt">
                {/* Named from text, not a composed attribute: the radio reads
                    "Original, <file>" in the reader's language. */}
                <span id="dl-guide-original" className="bn-sr-only">{S.original}</span>
                <span id="dl-guide-file-name" className="bn-sr-only">{data.guide_file}</span>
                <input type="radio" name="dl-guide-view" value="original" checked={guideView === "original"}
                  aria-labelledby="dl-guide-original dl-guide-file-name" onChange={() => setGuideView("original")} />
                {isExportMode() ? (
                  <span className="dl-guide-file" title={data.guide_file}>{formatFinderFilename(data.guide_file, 28)}</span>
                ) : (
                  <button type="button" className="dl-guide-file" title={`${S.chooseOtherGuide}: ${data.guide_file}`}
                    aria-label={S.chooseOtherGuide} onClick={chooseGuide}>
                    {formatFinderFilename(data.guide_file, 28)}
                  </button>
                )}
              </span>
            ) : (
              <label>
                <input type="radio" name="dl-guide-view" value="original" checked={guideView === "original"}
                  onChange={() => setGuideView("original")} />
                {S.original}
              </label>
            )}
          </div>
        )}
        {adding && !isExportMode() && !guide.pendingGuide && (
          // No guide: the second tab is where one is added. The Mac opens its
          // native panel, copies the guide in and re-runs (plan §4); a browser
          // cannot write into the project folder, so it says where the guide goes.
          // The heading is the navigator's own section heading (4 Oct 2026 copy).
          <div role="group" aria-labelledby="dl-h-add-guide">
            <h2 id="dl-h-add-guide" className="toc-heading">{S.addGuideHeading}</h2>
            <p className="dl-before">{S.addGuideIntro}</p>
            <p className="dl-before">{S.addGuideFormats}</p>
            {guideButton(data.guide_problem ? S.replaceGuide : S.addGuide)}
          </div>
        )}
        {shownSections.length > 0 && showKey && (
          // The key first, so it scrolls away (4 Oct 2026). Only the marks this
          // view uses: with no guide uploaded, none, so only the grey line. The classes are the
          // Settings ▸ Pipeline symbol key's; the marks are the rows' own.
          <div className="bn-pipeline-key dl-key" role="note" aria-label={S.key}>
            {keyMarks.size > 0 && (
            <div className="bn-pipeline-key-group">
              {keyMarks.has("dot") && (
                <span className="bn-pipeline-key-item">
                  <span className="dl-mk" aria-hidden="true"><span className="dl-dot" /></span>{S.keyBoth}
                </span>
              )}
              {keyMarks.has("hollow") && (
                <span className="bn-pipeline-key-item">
                  <span className="dl-mk" aria-hidden="true"><span className="dl-dot hollow" /></span>{S.keyHollow}
                </span>
              )}
              {keyMarks.has("plus") && (
                <span className="bn-pipeline-key-item">
                  <span className="dl-mk" aria-hidden="true">+</span>{S.keyPlus}
                </span>
              )}
            </div>
            )}
            {tier !== "bar" && (
              // The measure's cells. Not asked and asked-with-no-quotes are drawn alike (18 Oct).
              <div className="bn-pipeline-key-group">
                <span className="bn-pipeline-key-item">
                  <span className="dl-cell s0" aria-hidden="true" />{S.notAsked}
                </span>
                <span className="bn-pipeline-key-item">
                  <span className="dl-cell s1" aria-hidden="true" /><span className="dl-cell s2" aria-hidden="true" />
                  <span className="dl-cell s3" aria-hidden="true" />{S.keyMeasure}
                </span>
              </div>
            )}
            {!all && (
              <div className="bn-pipeline-key-group">
                <span className="bn-pipeline-key-item dl-key-grey">{S.keyGrey}</span>
              </div>
            )}
          </div>
        )}
        {tier === "grid" && shownSections.length > 0 && (
          // The grid's column heads: one-digit compact badges, a 10–12 squeezed into the same
          // box. In All none is lit — All, in the bar, is the selection (variant A, 18 Oct).
          <div className="dl-grid-head" aria-hidden="true">
            <span className="dl-grid-head-l">{S.sessions}</span>
            <span className="dl-cells">
              {data.sessions.map((sess) => (
                <span key={sess.id} className={`dl-head-cell${sess.number >= 10 ? " wide" : ""}`}
                  title={sessionName(sess.id)}>
                  <span className={sess.id === session ? "bn-person-badge-here" : undefined}>
                    <PersonBadge code={String(sess.number)} role="participant" compact />
                  </span>
                </span>
              ))}
            </span>
            <span className="dl-head-bar" />
          </div>
        )}
        {shownSections.map(({ head, rows }) => (
          <div key={head.id} role="group" aria-labelledby={`dl-h-${head.id}`}>
            <h2 id={`dl-h-${head.id}`} className="toc-heading">
              {head.id === "standalone" ? S.standalone : head.title}
              {head.badge && <Badge text={S.instruction} variant="readonly" />}
            </h2>
            {rows.map(row)}
          </div>
        ))}
        {data.guide_problem && !isExportMode() && (
          // A guide that is there but went unread says so — never "no guide".
          <p className="dl-before" role="status">{S.guideProblem(data.guide_problem)}</p>
        )}
        {mode === "planned" && data.guide && !data.guide_file && !isExportMode() &&
          // A record from before the file name was kept: no link to click.
          guideButton(S.replaceGuide)}
        {guideNote && <p className="dl-before" role="status">{S.guideHowTo}</p>}
        {/* The grid's pitch: a one-digit head, laid out but never seen (fitMeasure). */}
        <span ref={probeRef} className="dl-head-probe" aria-hidden="true">
          <PersonBadge code="8" role="participant" compact />
        </span>
      </nav>

      <div ref={gutRef} className="dl-gut">
        <svg className="dl-wires" aria-hidden="true">
          {wires.map((w, i) => (
            <g key={`${w.a}|${w.b}|${i}`}>
              <path className={`dl-wire${w.stub ? " stub" : ""}${hotWire(w.a, w.b) ? " hot" : ""}`} d={w.d} />
              {!w.stub && <circle className={`dl-end${hotWire(w.a, w.b) ? " hot" : ""}`} cx={0} cy={w.y1} r={2} />}
            </g>
          ))}
        </svg>
        {/* The shipped .drag-handle, on the navigator's edge. A focusable
            separator is an interactive widget (ARIA window splitter); the shared
            sidebar's handles carry the same disable. */}
        {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
        <div className={`drag-handle dl-split${dragging ? " active" : ""}${splitHover ? " hover-intent" : ""}`}
          role="separator" aria-orientation="vertical" aria-label={S.resize} aria-controls="dl-nav" tabIndex={0}
          aria-valuemin={MIN_WIDTH} aria-valuemax={Math.round(navMax)}
          aria-valuenow={Math.min(Math.round(navMax), effectiveW ?? Math.round(sizes.nav))}
          aria-valuetext={S.resizeText(Math.round((100 * (effectiveW ?? sizes.nav)) / Math.max(sizes.lens, 1)))}
          onPointerDown={onSplitDown} onKeyDown={onSplitKey}
          onPointerEnter={() => setSplitHover(true)} onPointerLeave={() => setSplitHover(false)} />
      </div>

      <div ref={contentRef} className="dl-content">
        {all && allColumn()}
        {current && (
          <section>
            <SectionHeading>{S.session(current.number)}</SectionHeading>
            <div className="dl-meta">
              {current.participants.map((p) => (
                <PersonBadge key={p.code} code={p.code} role="participant" name={p.name} />
              ))}
              <span className="dl-stats">{S.stats(current.duration, stats.questions, stats.quotes)}</span>
            </div>
            {current.state && current.state !== "ok" ? (
              <p className="dl-before" role="note">{S.sessionState(current.state)}</p>
            ) : (
              column.groups.length === 0 && <p className="dl-before">{S.noQuestions}</p>
            )}
            {column.before.length > 0 && (
              <div className="dl-group">
                {column.groups.length > 0 && <div className="dl-before">{S.before}</div>}
                {column.before.map((q) => quoteCard(q, ""))}
              </div>
            )}
            {column.groups.map((g) => {
              const last = g.asks[g.asks.length - 1].turn.id;
              return (
                <div key={g.asks[0].turn.id} className="dl-group">
                  {g.asks.map(({ turn, answers }) => [
                    askRow(turn, g.trailing && turn.id === last),
                    ...answers.map((q) => quoteCard(q, turn.id)),
                  ])}
                </div>
              );
            })}
          </section>
        )}
      </div>
    </div>
  );
}
