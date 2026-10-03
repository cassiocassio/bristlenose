/**
 * Discussion lens — the researcher's line of enquiry as planned and as asked,
 * with every participant's answers under the question that drew them.
 *
 * DEV-GATED (docs/design-discussion-lens-plan.md, Phase 4 behind IS_DEV). It
 * reads synthetic data through loadDiscussion(); quote cards are read-only
 * (star, hide and tag arrive with QuoteGroup once quotes have store ids), and
 * the copy is English until Phase 6. Mockup it was built from:
 * the private discussion-lens-runs/lens.html.
 *
 * Interaction (decided 3 Oct 2026): focus is sticky and click-driven — a
 * navigator row or a question locks focus until clicked again or Esc; nothing
 * reacts to the pointer passing over. Planned | Merged switches the navigator.
 * Narrow windows keep the session column and drop the navigator.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { PersonBadge } from "../../components/PersonBadge";
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
  type NavRow,
  type WireEnd,
} from "./model";
import { loadDiscussion } from "./loadDiscussion";
import type { DiscussionData, DiscussionQuote, DiscussionSession, DiscussionTurn } from "./types";
import "./discussion.css";

/** English until Phase 6 moves these to locale keys. */
const S = {
  show: "Show",
  planned: "Planned",
  merged: "Merged",
  sessions: "Sessions",
  navigator: "Discussion guide",
  instruction: "instruction",
  newSection: "new",
  session: (n: number) => `Session ${n}`,
  stats: (d: string, q: number, n: number) =>
    `${d} · ${q} ${q === 1 ? "question" : "questions"} · ${n} ${n === 1 ? "quote" : "quotes"}`,
  noAnswers: "No quotes from this question",
  before: "Before the first question",
  noGuide: "This project has no discussion guide. Merged shows every question asked.",
  others: (first: string, n: number) => `${first} and ${n} ${n === 1 ? "other" : "others"}`,
  askedIn: (n: number) => `Asked in ${n} sessions — show a session`,
  showSession: (n: number, names: string) => `Session ${n}: ${names}`,
  resize: "Resize the discussion guide",
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
const NAV_KEY = "bn-discussion-nav-width";

function readNavWidth(): number | null {
  try {
    const v = Number(localStorage.getItem(NAV_KEY));
    return Number.isFinite(v) && v >= MIN_WIDTH ? v : null;
  } catch {
    return null;
  }
}

function writeNavWidth(w: number): void {
  try {
    localStorage.setItem(NAV_KEY, String(Math.round(w)));
  } catch {
    // private window or blocked storage: the width just isn't remembered
  }
}

export function DiscussionLens() {
  const [data, setData] = useState<DiscussionData | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    loadDiscussion().then(
      (d) => live && setData(d),
      (e: unknown) => live && setError(e instanceof Error ? e.message : String(e)),
    );
    return () => {
      live = false;
    };
  }, []);
  if (error) return <p className="dl-empty" role="alert">{error}</p>;
  if (!data) return null;
  return <DiscussionView data={data} />;
}

export function DiscussionView({ data }: { data: DiscussionData }) {
  const order = useMemo(() => data.sessions.map((s) => s.id), [data]);
  const [mode, setMode] = useState<Mode>("merged");
  const [session, setSession] = useState<string>(order[0] ?? "");
  const [focus, setFocus] = useState<Focus | null>(null);
  const [navW, setNavW] = useState<number | null>(readNavWidth);
  const [compact, setCompact] = useState<Set<string>>(new Set());
  // Measured in the same frame as the wires — never read from the DOM during render.
  const [sizes, setSizes] = useState<{ lens: number; nav: number }>({ lens: 1000, nav: MIN_WIDTH });
  const [wires, setWires] = useState<{ d: string; stub: boolean; a: string; b: string; y1: number }[]>([]);

  const lensRef = useRef<HTMLDivElement>(null);
  const barRef = useRef<HTMLDivElement>(null);
  const navRef = useRef<HTMLElement>(null);
  const gutRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

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
  // The ONE place a participant's name is resolved — Phase 3 swaps it for /people,
  // so an anonymised export never carries names in the discussion payload.
  const namesOf = useCallback(
    (s: DiscussionSession) =>
      capNames(s.participants, (n) => (list ? list.format(n) : n.join(", ")), S.others),
    [list],
  );
  const fullNames = useCallback(
    (s: DiscussionSession) => {
      const n = s.participants.map((p) => p.name);
      return list ? list.format(n) : n.join(", ");
    },
    [list],
  );
  const byId = useMemo(() => new Map(data.sessions.map((s) => [s.id, s])), [data]);
  const num = (sid: string) => byId.get(sid)?.number ?? 0;

  const entries = useMemo(() => navEntries(data, mode), [data, mode]);
  const column = useMemo(() => sessionColumn(data, session), [data, session]);
  const stats = useMemo(() => sessionStats(data, session), [data, session]);
  const lit = useMemo(() => litTurns(data, session, focus), [data, session, focus]);
  const current = byId.get(session);

  // ── selection & focus ──
  const selectSession = useCallback((sid: string) => {
    setSession(sid);
    // a question is per session; keep its topic, drop the specific ask
    setFocus((f) => (f && f.turn ? { item: f.item, turn: null } : f));
  }, []);

  const focusRow = useCallback(
    (row: NavRow) => {
      setFocus((f) => {
        if (f && f.item === row.id && !f.turn) return null;
        return { item: row.id, turn: null };
      });
      setSession((s) => sessionForFocus(s, row.sessions));
    },
    [],
  );

  const focusAsk = useCallback((turn: DiscussionTurn) => {
    setFocus((f) => (f && f.turn === turn.id ? null : { item: turn.item ?? "", turn: turn.id }));
  }, []);

  // Esc clears focus; 1–9 pick a session. Never claims a key someone else handled.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.ctrlKey || e.altKey) return;
      // the target can be the document itself, which has no closest()
      const t = e.target;
      if (t instanceof Element && t.closest("input, textarea, select, [contenteditable='true']")) return;
      if (e.key === "Escape" && focus) {
        setFocus(null);
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

  // ── geometry: bar height, chip collapse, wires ──
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
      const chips = r.querySelector<HTMLElement>(".dl-chips");
      // measure the full row of badges even when it is currently collapsed
      if (chips && chips.scrollWidth > limit) next.add(r.dataset.id ?? "");
    });
    setCompact((prev) => (prev.size === next.size && [...next].every((x) => prev.has(x)) ? prev : next));
  }, []);

  const drawWires = useCallback(() => {
    const gut = gutRef.current, nav = navRef.current, content = contentRef.current;
    if (!gut || !nav || !content || gut.offsetParent === null) {
      setWires((w) => (w.length ? [] : w));
      return;
    }
    const g = gut.getBoundingClientRect();
    const nb = nav.getBoundingClientRect();
    const end = (el: Element, top: number, bottom: number): WireEnd => {
      const b = el.getBoundingClientRect();
      const y = b.top + Math.min(b.height / 2, 11);
      return { y: y - g.top, off: y < top + 4 ? -1 : y > bottom - 6 ? 1 : 0 };
    };
    const out: { d: string; stub: boolean; a: string; b: string; y1: number }[] = [];
    content.querySelectorAll<HTMLElement>(".dl-ask[data-item]").forEach((q) => {
      const item = q.dataset.item ?? "";
      const row = nav.querySelector(`.dl-row[data-id="${CSS.escape(item)}"]`);
      if (!row) return;
      const anchor = q.querySelector(".quote-row") ?? q;
      const from = end(row, nb.top, nb.bottom);
      const to = end(anchor, g.top, window.innerHeight);
      const p = wirePath(from, to, g.width);
      if (p) out.push({ ...p, a: item, b: q.dataset.turn ?? "", y1: from.y });
    });
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
  }, [fitChips, drawWires, entries, column, navW, compact]);

  // ── the split ──
  const navMax = () => Math.max(MIN_WIDTH, NAV_MAX_SHARE * sizes.lens);
  const setWidth = (w: number) => {
    const v = Math.round(Math.min(navMax(), Math.max(MIN_WIDTH, w)));
    setNavW(v);
    writeNavWidth(v);
  };
  const [dragging, setDragging] = useState(false);
  const onSplitDown = (e: React.PointerEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startW = navRef.current?.getBoundingClientRect().width ?? MIN_WIDTH;
    setDragging(true);
    const move = (ev: PointerEvent) => setWidth(startW + ev.clientX - startX);
    const up = () => {
      setDragging(false);
      window.removeEventListener("pointermove", move);
      window.removeEventListener("pointerup", up);
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };
  const onSplitKey = (e: React.KeyboardEvent) => {
    const w = navRef.current?.getBoundingClientRect().width ?? MIN_WIDTH;
    const step = { ArrowLeft: -RESIZE_STEP, ArrowRight: RESIZE_STEP } as Record<string, number>;
    if (e.key in step) setWidth(w + step[e.key]);
    else if (e.key === "Home") setWidth(MIN_WIDTH);
    else if (e.key === "End") setWidth(navMax());
    else return;
    e.preventDefault();
  };

  // ── render ──
  const sessionBadge = (sid: string, label?: string) => (
    <span className={sid === session ? "dl-here" : undefined}>
      <PersonBadge code={`#${num(sid)}`} role="participant" name={label} highlighted={sid === session} />
    </span>
  );

  const row = (r: NavRow) => {
    const asked = r.sessions.includes(session);
    const cls = ["toc-link", "dl-row"];
    if (!asked) cls.push(r.sessions.length ? "ghost" : "dim");
    if (r.mark === "hollow") cls.push("unasked");
    if (focus && focus.item === r.id) cls.push("active");
    if (compact.has(r.id)) cls.push("compact");
    const shown = r.sessions.length ? shownSession(session, r.sessions) : null;
    return (
      <div key={r.id} className={cls.join(" ")} data-id={r.id}>
        <button type="button" className="dl-row-btn" title={r.title}
          aria-pressed={!!focus && focus.item === r.id && !focus.turn} onClick={() => focusRow(r)}>
          <span className="dl-mk" aria-hidden="true">
            {r.mark === "plus" ? "+" : <span className={r.mark === "hollow" ? "dl-dot hollow" : "dl-dot"} />}
          </span>
          <span className="dl-tx">{r.text}</span>
        </button>
        {r.sessions.length > 0 && (
          <>
            <span className="dl-chips">
              {r.sessions.map((sid) => (
                <button key={sid} type="button" className="dl-chip"
                  aria-label={S.showSession(num(sid), fullNames(byId.get(sid)!))}
                  aria-pressed={sid === session}
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
                <PersonBadge code={`#${num(shown!)} ▾`} role="participant" highlighted={shown === session} />
              </span>
              <select aria-label={S.askedIn(r.sessions.length)} value={shown ?? ""}
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
              <span className={`badge badge-ai badge-${q.sentiment}`}>{q.sentiment}</span>
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
            <PersonBadge code="m1" role="moderator" />
          </span>
          {noAnswers && <span className="dl-noans">{S.noAnswers}</span>}
        </div>
      </div>
    </blockquote>
  );

  const hotWire = (a: string, b: string) =>
    !!focus && (focus.turn ? focus.turn === b : focus.item === a && lit.has(b));

  const style = navW ? ({ "--dl-nav-w": `${navW}px` } as React.CSSProperties) : undefined;

  return (
    <div ref={lensRef} className={`dl-lens${focus ? " has-focus" : ""}`} style={style} data-testid="discussion-lens">
      <div ref={barRef} className="dl-bar">
        <span className="dimension-toggle" role="radiogroup" aria-label={S.show}>
          {(["planned", "merged"] as const).map((m) => (
            <button key={m} type="button" role="radio" aria-checked={mode === m}
              className={`dimension-btn${mode === m ? " active" : ""}`} onClick={() => setMode(m)}>
              {m === "planned" ? S.planned : S.merged}
            </button>
          ))}
        </span>
        <div className="dl-sessions" role="radiogroup" aria-label={S.sessions}>
          {data.sessions.map((s) => (
            <button key={s.id} type="button" role="radio" aria-checked={s.id === session} className="dl-sess"
              title={S.showSession(s.number, fullNames(s))} onClick={() => selectSession(s.id)}>
              {sessionBadge(s.id, namesOf(s))}
            </button>
          ))}
        </div>
      </div>

      <nav ref={navRef} className="dl-nav toc-sidebar-body" aria-label={S.navigator}>
        {mode === "planned" && !data.guide && <p className="dl-empty">{S.noGuide}</p>}
        {entries.map((e) =>
          e.type === "head" ? (
            <div key={`h-${e.id}`} className="toc-heading">
              {e.title}
              {e.badge && <span className="badge">{e.badge === "instruction" ? S.instruction : S.newSection}</span>}
            </div>
          ) : (
            row(e)
          ),
        )}
      </nav>

      <div ref={gutRef} className="dl-gut" aria-hidden="true">
        <svg className="dl-wires">
          {wires.map((w, i) => (
            <g key={`${w.a}|${w.b}|${i}`}>
              <path className={`dl-wire${w.stub ? " stub" : ""}${hotWire(w.a, w.b) ? " hot" : ""}`} d={w.d} />
              {!w.stub && <circle className={`dl-end${hotWire(w.a, w.b) ? " hot" : ""}`} cx={0} cy={w.y1} r={2} />}
            </g>
          ))}
        </svg>
      </div>
      {/* A focusable separator is an interactive widget (ARIA "window splitter");
          the shared sidebar's drag handles carry the same disable. */}
      {/* eslint-disable-next-line jsx-a11y/no-noninteractive-element-interactions */}
      <div className={`dl-split${dragging ? " dragging" : ""}`} role="separator" aria-orientation="vertical"
        aria-label={S.resize} tabIndex={0} aria-valuemin={MIN_WIDTH} aria-valuemax={Math.round(navMax())}
        aria-valuenow={Math.round(navW ?? sizes.nav)}
        onPointerDown={onSplitDown} onKeyDown={onSplitKey} />

      <div ref={contentRef} className="dl-content">
        {current && (
          <section>
            <div className="section-heading">
              <h1>{S.session(current.number)}</h1>
            </div>
            <div className="dl-meta">
              {current.participants.map((p) => (
                <PersonBadge key={p.code} code={p.code} role="participant" name={p.name} />
              ))}
              <span className="dl-stats">{S.stats(current.duration, stats.questions, stats.quotes)}</span>
            </div>
            {column.before.length > 0 && (
              <div className="dl-group">
                <div className="dl-before">{S.before}</div>
                {column.before.map((q) => quoteCard(q, ""))}
              </div>
            )}
            {column.groups.map((g) => {
              const last = g.asks[g.asks.length - 1].turn.id;
              return (
                <div key={g.asks[0].turn.id} className="dl-group quote-group">
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
