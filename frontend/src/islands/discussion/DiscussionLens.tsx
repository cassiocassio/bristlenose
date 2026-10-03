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
 * reacts to the pointer passing over. Planned | Merged switches the navigator
 * (Merged only when there is no guide). Narrow windows keep the session column.
 * Focus is shown by the shipped active and selection styles, never by dimming
 * the rest: opacity drops readable text below AA (review, 3 Oct 2026).
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n";
import { Badge } from "../../components/Badge";
import { PersonBadge } from "../../components/PersonBadge";
import { SectionHeading } from "../../components/SectionHeading";
import { announce } from "../../utils/announce";
import { isExportMode } from "../../utils/exportData";
import { dt } from "../../utils/platformTranslation";
import { isEmbedded } from "../../utils/embedded";
import { postProjectAction } from "../../shims/bridge";
import { MIN_WIDTH, RESIZE_STEP } from "./split";
import {
  capNames,
  litTurns,
  navEntries,
  sessionColumn,
  sessionForFocus,
  sessionStats,
  shownSession,
  wirePath,
  type Focus,
  type GuideView,
  type Mode,
  type NavEntry,
  type NavRow,
  type WireEnd,
} from "./model";
import { loadDiscussion, type DiscussionLoad } from "./loadDiscussion";
import { readLensState, writeLensState } from "./lensState";
import type { DiscussionData, DiscussionQuote, DiscussionSession, DiscussionTurn } from "./types";
import "./discussion.css";

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
  get before() { return d("before"); },
  get noQuestions() { return d("noQuestions"); },
  get noSessions() { return d("noSessions"); },
  get unclassified() { return d("unclassified"); },
  others: (first: string, n: number) => d("others", { first, count: n }),
  askedIn: (n: number) => d("askedIn", { count: n }),
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

const CHIP_SHARE = 0.3;      // a row's badges collapse past 30% of the navigator's width
const NAV_MAX_SHARE = 0.6;   // the navigator may widen to 60% of the lens

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
  const [mode, setMode] = useState<Mode>(data.guide ? saved.mode : "merged");
  const [guideView, setGuideView] = useState<GuideView>(saved.guideView);
  const [guideNote, setGuideNote] = useState(false);
  const [session, setSession] = useState<string>(
    saved.session && order.includes(saved.session) ? saved.session : (order[0] ?? ""),
  );
  const [focus, setFocus] = useState<Focus | null>(saved.focus);
  const [navW, setNavW] = useState<number | null>(saved.navWidth);
  const [compact, setCompact] = useState<Set<string>>(new Set());
  // Measured in the same frame as the wires — never read from the DOM during render.
  const [sizes, setSizes] = useState<{ lens: number; nav: number }>({ lens: 1000, nav: MIN_WIDTH });
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
  const natural = useRef(new Map<string, number>()); // each row's badges at full width
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

  // ── selection & focus ──
  const selectSession = useCallback(
    (sid: string) => {
      setSession(sid);
      // a question is per session; keep its topic, drop the specific ask
      setFocus((f) => (f && f.turn ? { item: f.item, turn: null } : f));
      announce(S.announceSession(num(sid), data.turns.filter((t) => t.session === sid && t.item).length));
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

  // Bring the first lit question into view when a navigator row takes focus.
  useEffect(() => {
    if (!focus || focus.turn) return;
    const el = contentRef.current?.querySelector<HTMLElement>(".dl-ask.hot");
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

  const fitChips = useCallback(() => {
    const nav = navRef.current;
    if (!nav) return;
    const limit = CHIP_SHARE * nav.clientWidth;
    const next = new Set<string>();
    nav.querySelectorAll<HTMLElement>(".dl-row").forEach((r) => {
      const id = r.dataset.id ?? "";
      const chips = r.querySelector<HTMLElement>(".dl-chips");
      if (!chips) return;
      // A collapsed row's badges are display:none and measure 0 — so measure only
      // while they are shown, and remember. (Measuring the hidden row flipped it
      // open and shut every frame: review, 3 Oct 2026.)
      if (!r.classList.contains("compact") && chips.scrollWidth > 0) natural.current.set(id, chips.scrollWidth);
      if ((natural.current.get(id) ?? 0) > limit) next.add(id);
    });
    setCompact((prev) => (prev.size === next.size && [...next].every((x) => prev.has(x)) ? prev : next));
  }, []);

  const drawWires = useCallback(() => {
    const gut = gutRef.current, nav = navRef.current, content = contentRef.current;
    const out: Wire[] = [];
    if (gut && nav && content && gut.offsetParent !== null) {
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
        if (lens) setSizes((p) => (p.lens === lens && p.nav === nav ? p : { lens, nav }));
        fitChips();
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
  }, [fitChips, drawWires, entries, column, navW]);

  // ── the split ──
  const navMax = Math.max(MIN_WIDTH, NAV_MAX_SHARE * sizes.lens);
  const clamp = (w: number) => Math.round(Math.min(navMax, Math.max(MIN_WIDTH, w)));
  // A width saved on a wider window is pulled back to this one's ceiling.
  const effectiveW = navW === null ? null : clamp(navW);
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
    <span className={sid === session ? "dl-here" : undefined}>
      <PersonBadge code={`#${num(sid)}`} role="participant" name={label} />
    </span>
  );

  const markTip = (r: NavRow) =>
    mode === "planned" ? S.tipPlanned
      : r.mark === "dot" ? S.tipBoth : r.mark === "hollow" ? S.tipHollow : S.tipPlus;

  const markText = (r: NavRow) =>
    mode === "planned" ? S.markPlanned
      : r.mark === "dot" ? S.markBoth : r.mark === "hollow" ? S.markHollow : S.markPlus;

  const row = (r: NavRow) => {
    const asked = r.sessions.includes(session);
    const on = !!focus && focus.item === r.id;
    const cls = ["toc-link", "dl-row"];
    if (!asked) cls.push(r.sessions.length ? "ghost" : "dim");
    if (r.mark === "hollow") cls.push("unasked");
    if (on) cls.push("active");
    if (compact.has(r.id)) cls.push("compact");
    const shown = r.sessions.length ? shownSession(session, r.sessions) : null;
    return (
      <div key={r.id} className={cls.join(" ")} data-id={r.id}>
        <button type="button" className="dl-row-btn" title={r.title} onClick={() => focusRow(r)}
          aria-pressed={r.sessions.length ? on : undefined} aria-disabled={r.sessions.length ? undefined : true}>
          <span className="dl-mk" aria-hidden="true" title={markTip(r)}>
            {r.mark === "plus" ? "+" : <span className={r.mark === "hollow" ? "dl-dot hollow" : "dl-dot"} />}
          </span>
          <span className="dl-tx">{r.text}</span>
          <span className="bn-sr-only">{`, ${markText(r)}${asked || !r.sessions.length ? "" : S.notHere(num(session))}`}</span>
        </button>
        {shown && (
          <>
            <span className="dl-chips">
              {r.sessions.map((sid) => (
                <button key={sid} type="button" className="dl-chip"
                  aria-label={S.sessionLabel(num(sid), fullNames(byId.get(sid)!))}
                  aria-current={sid === session ? "true" : undefined}
                  onClick={() => {
                    selectSession(sid);
                    setFocus({ item: r.id, turn: null });
                  }}>
                  {sessionBadge(sid)}
                </button>
              ))}
            </span>
            <span className="dl-pick">
              <span className={shown === session ? "dl-here" : undefined} aria-hidden="true">
                <PersonBadge code={`#${num(shown)} ▾`} role="participant" />
              </span>
              <select aria-label={S.askedIn(r.sessions.length)} value={shown}
                onChange={(e) => {
                  selectSession(e.target.value);
                  setFocus({ item: r.id, turn: null });
                }}>
                {r.sessions.map((sid) => (
                  <option key={sid} value={sid}>{`#${num(sid)} — ${namesOf(byId.get(sid)!)}`}</option>
                ))}
              </select>
            </span>
          </>
        )}
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

  const style = effectiveW ? ({ "--dl-nav-w": `${effectiveW}px` } as React.CSSProperties) : undefined;
  // Normalised questions first: it is the view the lens opens on.
  const modes: Mode[] = ["merged", "planned"];

  return (
    <div ref={lensRef} className={`dl-lens${focus ? " has-focus" : ""}`} style={style} data-testid="discussion-lens">
      <div ref={barRef} className="dl-bar">
        {data.guide ? (
          <span className="dimension-toggle" role="radiogroup" aria-label={S.show}>
            {modes.map((m) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} data-value={m}
                tabIndex={mode === m ? 0 : -1} onKeyDown={(e) => onRadioKeys(e, modes, mode, setMode)}
                title={m === "planned" ? S.plannedTip : S.mergedTip}
                className={`dimension-btn${mode === m ? " active" : ""}`} onClick={() => setMode(m)}>
                {m === "planned" ? S.planned : S.merged}
              </button>
            ))}
          </span>
        ) : (
          <span />
        )}
        <div className="dl-sessions" role="radiogroup" aria-label={S.sessions}>
          {data.sessions.map((s) => (
            <button key={s.id} type="button" role="radio" aria-checked={s.id === session} data-value={s.id}
              tabIndex={s.id === session ? 0 : -1} className="dl-sess"
              onKeyDown={(e) => onRadioKeys(e, order, session, selectSession)}
              aria-label={S.sessionLabel(s.number, fullNames(s))} title={fullNames(s) ? `${S.session(s.number)}: ${fullNames(s)}` : S.session(s.number)}
              onClick={() => selectSession(s.id)}>
              {sessionBadge(s.id, namesOf(s))}
            </button>
          ))}
        </div>
      </div>

      <nav ref={navRef} id="dl-nav" className="dl-nav toc-sidebar-body" aria-label={S.navigator}>
        {mode === "planned" && data.guide && (
          // Native radios: arrow keys and announcement come with the element.
          <div className="dl-guide-view" role="radiogroup" aria-label={S.guideView}>
            {(["summary", "original"] as const).map((v) => (
              <label key={v}>
                <input type="radio" name="dl-guide-view" value={v} checked={guideView === v}
                  onChange={() => setGuideView(v)} />
                {v === "summary" ? S.summary : S.original}
              </label>
            ))}
          </div>
        )}
        {sections.map(({ head, rows }) => (
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
        {(mode === "planned" || !data.guide) && !isExportMode() && (
          // The house small secondary button at the foot of a navigator — the
          // Codebook navigator's Browse Library is the precedent. In the Mac app
          // it opens the native panel, which copies the guide in and re-runs
          // (plan §4); a browser has no way to write into the project folder,
          // so there it says where the guide goes.
          <>
            <button type="button" className="bn-btn bn-btn-secondary bn-btn-sm"
              onClick={() => (isEmbedded() ? postProjectAction("choose-discussion-guide") : setGuideNote(true))}>
              {data.guide || data.guide_problem ? S.replaceGuide : S.addGuide}
            </button>
            {guideNote && <p className="dl-before" role="status">{S.guideHowTo}</p>}
          </>
        )}
        {mode === "merged" && (
          // The Settings ▸ Pipeline symbol key, reused as is (its classes set the
          // type and spacing); the marks are the rows' own, so they match exactly.
          <div className="bn-pipeline-key dl-key" role="note" aria-label={S.key}>
            <div className="bn-pipeline-key-group">
              <span className="bn-pipeline-key-item">
                <span className="dl-mk" aria-hidden="true"><span className="dl-dot" /></span>{S.keyBoth}
              </span>
              <span className="bn-pipeline-key-item">
                <span className="dl-mk" aria-hidden="true"><span className="dl-dot hollow" /></span>{S.keyHollow}
              </span>
              <span className="bn-pipeline-key-item">
                <span className="dl-mk" aria-hidden="true">+</span>{S.keyPlus}
              </span>
            </div>
            <div className="bn-pipeline-key-group">
              <span className="bn-pipeline-key-item">{S.keyGrey}</span>
            </div>
          </div>
        )}
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
