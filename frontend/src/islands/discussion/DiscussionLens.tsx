/**
 * Discussion lens — the researcher's line of enquiry as planned and as asked,
 * with every participant's answers under the question that drew them.
 *
 * DEV-GATED (docs/design-discussion-lens-plan.md, Phase 4 behind IS_DEV; §9 has
 * what this preview settles and what it does not). It reads synthetic data
 * through loadDiscussion(); quote cards are read-only (star, hide and tag arrive
 * with QuoteGroup once quotes have store ids), and the copy is English until
 * Phase 6.
 *
 * Interaction (decided 3 Oct 2026): focus is sticky and click-driven — a
 * navigator row or a question locks focus until clicked again or Esc; nothing
 * reacts to the pointer passing over. Planned | Merged switches the navigator
 * (Merged only when there is no guide). Narrow windows keep the session column.
 * Focus is shown by the shipped active and selection styles, never by dimming
 * the rest: opacity drops readable text below AA (review, 3 Oct 2026).
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { Badge } from "../../components/Badge";
import { PersonBadge } from "../../components/PersonBadge";
import { SectionHeading } from "../../components/SectionHeading";
import { announce } from "../../utils/announce";
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
  type Mode,
  type NavEntry,
  type NavRow,
  type WireEnd,
} from "./model";
import { loadDiscussion } from "./loadDiscussion";
import { readLensState, writeLensState } from "./lensState";
import type { DiscussionData, DiscussionQuote, DiscussionSession, DiscussionTurn } from "./types";
import "./discussion.css";

/** English until Phase 6 moves these to locale keys. */
const S = {
  title: "Discussion",
  show: "Show",
  planned: "Planned",
  merged: "Merged",
  sessions: "Sessions",
  navigator: "Discussion guide",
  instruction: "instruction",
  newSection: "new",
  standalone: "Standalone",
  session: (n: number) => `Session ${n}`,
  stats: (d: string, q: number, n: number) =>
    `${d} · ${q} ${q === 1 ? "question" : "questions"} · ${n} ${n === 1 ? "quote" : "quotes"}`,
  noAnswers: "No quotes from this question",
  before: "Before the first question",
  noQuestions: "No questions found in this session",
  noSessions: "No sessions to show yet.",
  unclassified: "not classified",
  others: (first: string, n: number) => `${first} and ${n} ${n === 1 ? "other" : "others"}`,
  askedIn: (n: number) => `Asked in ${n} sessions — show a session`,
  sessionLabel: (n: number, names: string) => `#${n} ${names}`,
  resize: "Resize the discussion guide",
  resizeText: (pct: number) => `Guide ${pct}% of width`,
  loading: "Loading the discussion…",
  failed: "The discussion could not be loaded.",
  markPlanned: "planned",
  markBoth: "planned and asked",
  markHollow: "planned, never asked",
  markPlus: "not in the guide",
  notHere: (n: number) => `, not asked in session ${n}`,
  announceSession: (n: number, q: number) => `Session ${n}, ${q} ${q === 1 ? "question" : "questions"}`,
  announceFocus: (text: string) => `Focused on ${text}`,
  announceClear: "Focus cleared",
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

export function DiscussionLens() {
  const [data, setData] = useState<DiscussionData | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let live = true;
    loadDiscussion().then(
      (d) => live && setData(d),
      () => live && setFailed(true),
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
  if (!data) return shell(<p className="bn-empty-state" aria-busy="true">{S.loading}</p>);
  if (!data.sessions.length) return shell(<p className="bn-empty-state">{S.noSessions}</p>);
  return <DiscussionView data={data} />;
}

export function DiscussionView({ data }: { data: DiscussionData }) {
  const order = useMemo(() => data.sessions.map((s) => s.id), [data]);
  const saved = useMemo(() => readLensState(), []);
  const [mode, setMode] = useState<Mode>(data.guide ? saved.mode : "merged");
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
    if (!dragging) writeLensState({ mode, session, focus, navWidth: navW });
  }, [mode, session, focus, navW, dragging]);

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
    const lang = document.documentElement.lang || "en";
    try {
      return new ListFormat(lang === "en" ? "en-GB" : lang, { style: "long", type: "conjunction" });
    } catch {
      return null;
    }
  }, []);
  const join = useCallback((n: string[]) => (list ? list.format(n) : n.join(", ")), [list]);
  // The ONE place a participant's name is resolved — Phase 3 swaps it for /people,
  // so an anonymised export never carries names in the discussion payload (§9.C).
  const namesOf = useCallback((s: DiscussionSession) => capNames(s.participants, join, S.others), [join]);
  const fullNames = useCallback((s: DiscussionSession) => join(s.participants.map((p) => p.name)), [join]);
  const byId = useMemo(() => new Map(data.sessions.map((s) => [s.id, s])), [data]);
  const num = useCallback((sid: string) => byId.get(sid)?.number ?? 0, [byId]);

  const entries = useMemo(() => navEntries(data, mode), [data, mode]);
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
      <PersonBadge code={`#${num(sid)}`} role="participant" name={label} highlighted={sid === session} />
    </span>
  );

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
        <button type="button" className="dl-row-btn" title={r.title} aria-pressed={on} onClick={() => focusRow(r)}>
          <span className="dl-mk" aria-hidden="true">
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
                <PersonBadge code={`#${num(shown)} ▾`} role="participant" highlighted={shown === session} />
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
  const modes: Mode[] = ["planned", "merged"];

  return (
    <div ref={lensRef} className={`dl-lens${focus ? " has-focus" : ""}`} style={style} data-testid="discussion-lens">
      <div ref={barRef} className="dl-bar">
        {data.guide ? (
          <span className="dimension-toggle" role="radiogroup" aria-label={S.show}>
            {modes.map((m) => (
              <button key={m} type="button" role="radio" aria-checked={mode === m} data-value={m}
                tabIndex={mode === m ? 0 : -1} onKeyDown={(e) => onRadioKeys(e, modes, mode, setMode)}
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
              aria-label={S.sessionLabel(s.number, fullNames(s))} title={`${S.session(s.number)}: ${fullNames(s)}`}
              onClick={() => selectSession(s.id)}>
              {sessionBadge(s.id, namesOf(s))}
            </button>
          ))}
        </div>
      </div>

      <nav ref={navRef} id="dl-nav" className="dl-nav toc-sidebar-body" aria-label={S.navigator}>
        {sections.map(({ head, rows }) => (
          <div key={head.id} role="group" aria-labelledby={`dl-h-${head.id}`}>
            <h2 id={`dl-h-${head.id}`} className="toc-heading">
              {head.id === "standalone" ? S.standalone : head.title}
              {head.badge && <Badge text={head.badge === "instruction" ? S.instruction : S.newSection} variant="readonly" />}
            </h2>
            {rows.map(row)}
          </div>
        ))}
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
            {column.groups.length === 0 && <p className="dl-before">{S.noQuestions}</p>}
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
