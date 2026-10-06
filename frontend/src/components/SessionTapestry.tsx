/**
 * SessionTapestry — the timeline slice under a row of the Sessions grid.
 *
 * Five lanes on one time axis: section flags (top border), speaker clips on a
 * moderator and a participant track, sentiment bars (positive above the line,
 * negative below, surprise on it), and theme spans (bottom border). Hovering
 * the speaker lane raises that stretch's section flag in full; clicking the
 * lane, a flag or the quote panel jumps to the transcript.
 *
 * Data: GET /api/projects/{id}/tapestry (server/routes/tapestry.py). Clip
 * colour is the pipeline's per-turn scene colour (utils/scene_colour.py) —
 * what was on screen, never a colour for the speaker; the track says who.
 * Design + measurements: experiments/session-tapestry/README.md.
 *
 * Lazy-loaded by SessionsTable (the Sessions lens is on the first-paint path,
 * a slice is not); never re-export it from components/index.ts. The scale
 * helpers the table needs eagerly live in utils/tapestryScale.ts.
 */

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "./Badge";
import type { TapestryQuote, TapestrySession } from "../utils/types";
import { TAPESTRY_GUTTER, TAPESTRY_RIGHT as RIGHT } from "../utils/tapestryScale";
import { formatTimecode } from "../utils/format";
import { announce } from "../utils/announce";

/** Clips are drawn as rounded clips at or below this many seconds per pixel, as slivers above it. */
const CLIP_THRESHOLD = 2.5;
const POSITIVE = new Set(["satisfaction", "delight", "confidence"]);

// ── Text fitting: measured with the fonts the SVG classes render in ───────
let measureCtx: CanvasRenderingContext2D | null | undefined;
const widths = new Map<string, number>(); // labels repeat across renders; measure each once
function measure(text: string, font: string): number {
  const key = `${font}\u0000${text}`;
  const cached = widths.get(key);
  if (cached !== undefined) return cached;
  const w = measureRaw(text, font);
  widths.set(key, w);
  return w;
}
function measureRaw(text: string, font: string): number {
  if (measureCtx === undefined) {
    try {
      measureCtx = document.createElement("canvas").getContext("2d");
    } catch {
      measureCtx = null; // jsdom has no canvas
    }
  }
  if (!measureCtx) return text.length * 6.5;
  measureCtx.font = font;
  return measureCtx.measureText(text).width;
}
function fit(text: string, avail: number, font: string): string {
  if (avail < 10) return "";
  if (measure(text, font) <= avail) return text;
  let t = text;
  while (t.length > 1 && measure(t + "…", font) > avail) t = t.slice(0, -1);
  return t.length > 1 ? t + "…" : "";
}
function fonts(): { flag: string; tag: string; clip: string; lane: string } {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string, fallback: string) => cs.getPropertyValue(n).trim() || fallback;
  const px = (val: string) => (val.endsWith("rem") ? `${parseFloat(val) * 16}px` : val);
  const body = v("--bn-font-body", "system-ui, sans-serif");
  return {
    flag: `${v("--bn-weight-emphasis", "490")} ${px(v("--bn-text-badge", "11.5px"))} ${body}`,
    tag: `${v("--bn-weight-normal", "420")} ${px(v("--bn-text-badge", "11.5px"))} ${body}`,
    clip: `${v("--bn-weight-emphasis", "490")} ${px(v("--bn-text-micro", "9.6px"))} ${body}`,
    lane: `${v("--bn-weight-emphasis", "490")} ${px(v("--bn-text-caption", "12px"))} ${body}`,
  };
}

const isTeam = (code: string) => /^[mo]/.test(code);
/** WCAG relative luminance of an `#rrggbb` colour. */
function relLuminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  const lin = (c: number) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * lin((n >> 16) & 255) + 0.7152 * lin((n >> 8) & 255) + 0.0722 * lin(n & 255);
}
/** The label ink with the higher WCAG contrast against a scene-coloured clip. */
function inkOn(hex: string): string {
  const l = relLuminance(hex);
  const vsWhite = 1.05 / (l + 0.05);
  const vsDark = (l + 0.05) / (relLuminance("#1a1a1a") + 0.05);
  return vsWhite >= vsDark ? "#fff" : "#1a1a1a";
}

// Only one slice holds an open quote at a time, so ← → and Esc drive exactly one.
const ACTIVE_EVENT = "bn:tapestry-active";

interface Props {
  session: TapestrySession;
  sPerPx: number;
  /** Display name for a slot code; falls back to the code. */
  nameOf: (slot: string) => string;
  /** The displayed code for a slot; its first letter (m/o = team) picks the track. Defaults to the slot. */
  codeOf?: (slot: string) => string;
  onJump: (seconds: number) => void;
  /** This timeline's sideways scroll, restored on mount. */
  initialScrollLeft?: number;
}

export default function SessionTapestry({
  session, sPerPx, nameOf, codeOf = (slot) => slot, onJump, initialScrollLeft = 0,
}: Props) {
  const { t } = useTranslation();
  const svgRef = useRef<SVGSVGElement>(null);
  const [raised, setRaised] = useState(-1);
  // A flag directly under the pointer: selected-blue, full label, cursor at its time.
  const [hotFlag, setHotFlag] = useState(-1);
  const [playhead, setPlayhead] = useState<number | null>(null);
  const [selected, setSelected] = useState(-1);
  const [themeFocus, setThemeFocus] = useState<string | null>(null);
  const F = useMemo(() => fonts(), []);
  const panelId = `bn-tp-panel-${session.session_id}`;
  const wrapRef = useRef<HTMLDivElement>(null);
  const popRef = useRef<HTMLDivElement>(null);
  const [scrollLeft, setScrollLeft] = useState(0);
  const [pop, setPop] = useState<{ left: number; top: number; width: number; arrow: number } | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    if (scrollRef.current && initialScrollLeft) scrollRef.current.scrollLeft = initialScrollLeft;
    // Mount only: afterwards the researcher's own scrolling drives it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const choose = (i: number) => {
    setSelected(i);
    if (i >= 0) window.dispatchEvent(new CustomEvent(ACTIVE_EVENT, { detail: session.session_id }));
  };
  useEffect(() => {
    const other = (e: Event) => {
      if ((e as CustomEvent<string>).detail !== session.session_id) setSelected(-1);
    };
    window.addEventListener(ACTIVE_EVENT, other);
    return () => window.removeEventListener(ACTIVE_EVENT, other);
  }, [session.session_id]);
  // A refetch (a hide, a rename) can reorder quotes; an index would then name a different one.
  useEffect(() => {
    setSelected(-1);
  }, [session.quotes]);

  // Hover work is coalesced to one update per frame; a raw mousemove re-rendered every clip and bar.
  const pendingX = useRef<number | null>(null);
  const frame = useRef(0);
  useEffect(() => () => cancelAnimationFrame(frame.current), []);

  const s = session;
  // The server's per-turn answer wins (it reads the slot's role); otherwise the displayed code.
  const teamTurn = (tn: TapestrySession["turns"][number]) =>
    typeof tn.team === "boolean" ? tn.team : isTeam(codeOf(tn.speaker));
  const x = (sec: number) => TAPESTRY_GUTTER + sec / sPerPx;
  const xEnd = x(s.duration_seconds);
  const W = Math.ceil(xEnd + RIGHT);
  const clips = sPerPx <= CLIP_THRESHOLD;
  const MT = { y: 26, h: 16 };
  const PT = { y: 45, h: 18 };
  const SE = { mid: 104, amp: 30 };
  const TG = { y: 144, row: 19, rows: 3 };
  const H = TG.y + TG.row * TG.rows + 14;

  // While a quote is open, ← → step quotes and Esc closes, whatever has focus:
  // WebKit does not focus an SVG element on click, so a bar-scoped handler let
  // the arrow fall through to the slice's horizontal scroll.
  useEffect(() => {
    if (selected < 0) return;
    // Capture phase, like the modals: an open quote claims Esc before the app's global
    // cascade (selection, search) can spend it. A modal over the page wins: it makes the
    // app root inert, and then the timeline stands aside.
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.altKey || e.ctrlKey) return;
      if ((document.getElementById("bn-app-root") as (HTMLElement & { inert?: boolean }) | null)?.inert) return;
      const tgt = e.target as HTMLElement | null;
      if (tgt?.closest?.("input, textarea, select, [contenteditable='true']")) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        e.stopPropagation();
        choose(Math.max(0, Math.min(s.quotes.length - 1, selected + (e.key === "ArrowRight" ? 1 : -1))));
      } else if (e.key === "Escape") {
        e.preventDefault();
        e.stopPropagation();
        setSelected(-1);
      }
    };
    document.addEventListener("keydown", onKey, true);
    return () => document.removeEventListener("keydown", onKey, true);
    // choose is stable in behaviour; selected and the quote count are the inputs.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected, s.quotes.length]);

  // A click anywhere that is not a bar or the popover closes the quote, like a Mac popover.
  useEffect(() => {
    if (selected < 0) return;
    const onDown = (e: PointerEvent) => {
      const tgt = e.target as Element | null;
      if (tgt?.closest?.(".bn-tp-bar, .bn-tp-popover")) return;
      setSelected(-1);
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [selected]);

  // Keep the selected bar in view inside the horizontally scrolling slice; focus follows the
  // selection (clicking an SVG element does not focus it in WebKit); announce the change.
  useEffect(() => {
    if (selected < 0) return;
    const wrap = svgRef.current?.parentElement;
    const q = s.quotes[selected];
    if (!wrap || !q) return;
    const bar = svgRef.current?.querySelectorAll<SVGElement>(".bn-tp-bar")[selected];
    const active = document.activeElement;
    if (bar && (!active || active === document.body || svgRef.current?.contains(active)
      || document.getElementById(panelId)?.contains(active))) {
      bar.focus({ preventScroll: true });
    }
    const label = q.sentiment ? t(`enums:sentiment.${q.sentiment}`, { defaultValue: q.sentiment }) : "";
    announce([label, formatTimecode(q.t0), q.text.slice(0, 80)].filter(Boolean).join(", "));
    const bx = x(q.t0);
    if (bx < wrap.scrollLeft + 90 || bx > wrap.scrollLeft + wrap.clientWidth - 30) {
      wrap.scrollLeft = Math.max(0, bx - wrap.clientWidth / 2);
    }
    // x depends on sPerPx only; selected is the trigger.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected]);

  const secAt = (clientX: number) => {
    const left = svgRef.current?.getBoundingClientRect().left ?? 0;
    return Math.max(0, Math.min(s.duration_seconds, (clientX - left - TAPESTRY_GUTTER) * sPerPx));
  };
  const sectionAt = (sec: number) => {
    let i = -1;
    s.sections.forEach((f, k) => {
      if (f.t0 <= sec) i = k;
    });
    return i;
  };

  // Theme spans: first to last quote of each theme, packed into rows.
  const spans = useMemo(() => {
    const by = new Map<string, { t0: number; t1: number; n: number }>();
    for (const q of s.quotes) {
      if (!q.theme) continue;
      const sp = by.get(q.theme) ?? { t0: q.t0, t1: q.t0, n: 0 };
      sp.t0 = Math.min(sp.t0, q.t0);
      sp.t1 = Math.max(sp.t1, q.t0);
      sp.n += 1;
      by.set(q.theme, sp);
    }
    return [...by.entries()].sort((a, b) => a[1].t0 - b[1].t0);
  }, [s.quotes]);

  // The popover floats under its bar — over the themes track, not below the slice — with its
  // arrow on the bar. Measured after layout: the slice scrolls, the popover does not.
  const selQ = selected >= 0 ? s.quotes[selected] : undefined;
  useLayoutEffect(() => {
    const wrap = wrapRef.current;
    const svg = svgRef.current;
    if (!selQ || !wrap || !svg) {
      setPop(null);
      return;
    }
    const w = wrap.getBoundingClientRect();
    const g = svg.getBoundingClientRect();
    const barX = g.left - w.left + x(selQ.t0);
    const h = (0.35 + (0.65 * (Math.min(3, Math.max(1, selQ.intensity)) - 1)) / 2) * SE.amp;
    const below = selQ.sentiment && !POSITIVE.has(selQ.sentiment) && selQ.sentiment !== "surprise" ? SE.mid + h : SE.mid + 4;
    const width = Math.max(200, Math.min(440, (wrap.clientWidth || 440) - 16));
    const left = Math.max(8, Math.min(barX - 48, (wrap.clientWidth || width + 16) - width - 8));
    setPop({ left, top: g.top - w.top + below + 9, width, arrow: Math.max(14, Math.min(width - 14, barX - left)) });
    // x depends on sPerPx; scrollLeft moves the bar under a fixed popover.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selQ, sPerPx, scrollLeft]);

  // Lane labels are fitted to the gutter, so a long translation ellipsises rather than overruns.
  const lane = (label: string) => fit(label, TAPESTRY_GUTTER - 18, F.lane) || label.slice(0, 1);

  const tickStep = [60, 120, 300, 600, 900, 1800].find((st) => st / sPerPx >= 64) ?? 3600;
  // While hovering the speaker lane, the tick nearest the playhead lights up.
  const nearTick = playhead === null ? null : Math.round(playhead / tickStep) * tickStep;
  const ticks: number[] = [];
  for (let tk = 0; tk <= s.duration_seconds; tk += tickStep) ticks.push(tk);

  const top = hotFlag >= 0 ? hotFlag : raised;
  const flagOrder = s.sections.map((_, i) => i).filter((i) => i !== top);
  if (top >= 0) flagOrder.push(top); // raised or hot flag draws last, on top

  const themeEnds = Array(TG.rows).fill(-1e9) as number[];
  const sel: TapestryQuote | undefined = selQ;

  return (
    <div className="bn-tp-wrap" ref={wrapRef}>
      <div className="bn-tapestry-scroll" ref={scrollRef} onScroll={(e) => setScrollLeft(e.currentTarget.scrollLeft)}>
        <svg
          ref={svgRef}
          className="bn-tapestry-svg"
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          role="group"
          aria-label={t("sessions.tapestry.label")}
        >
          <defs>
            <filter id={`bn-tp-lift-${s.session_id}`} x="-10%" y="-30%" width="120%" height="170%">
              <feDropShadow dx={0} dy={0.6} stdDeviation={0.9} floodColor="#000" floodOpacity={0.16} />
            </filter>
          </defs>
          <text className="bn-tp-lane" x={12} y={14}>{lane(t("quotes.sections"))}</text>
          <text className="bn-tp-lane" x={12} y={MT.y + 12}>{lane(t("sessions.speakerPlaceholder.moderator"))}</text>
          <text className="bn-tp-lane" x={12} y={PT.y + 13}>{lane(t("sessions.speakerPlaceholder.participant"))}</text>
          <text className="bn-tp-lane" x={12} y={SE.mid + 3}>{lane(t("sessions.colSentiment"))}</text>
          <text className="bn-tp-lane" x={12} y={TG.y + 11}>{lane(t("quotes.themes"))}</text>

          {/* Speaker clips */}
          <rect className="bn-tp-track" x={TAPESTRY_GUTTER} y={MT.y - 1} width={Math.max(0, xEnd - TAPESTRY_GUTTER)}
            height={PT.y + PT.h - MT.y + 2} rx={4} />
          {s.turns.map((tn, i) => {
            const tr = teamTurn(tn) ? MT : PT;
            const x0 = x(tn.t0);
            const w = x(tn.t1) - x0;
            const cls = `bn-tp-clip ${teamTurn(tn) ? "bn-tp-clip-team" : "bn-tp-clip-ppt"}`;
            const style = tn.colour ? { fill: tn.colour } : undefined;
            if (!clips) {
              return <rect key={i} className={cls} style={style} x={x0} y={tr.y} width={Math.max(0.5, w)} height={tr.h} />;
            }
            if (w < 1) return null;
            const label = fit(nameOf(tn.speaker), w - 8, F.clip) || (w > 22 ? tn.speaker : "");
            const ink = tn.colour ? inkOn(tn.colour) : undefined;
            return (
              <g key={i}>
                <rect className={cls} style={style} x={x0 + 0.5} y={tr.y} width={Math.max(1, w - 1)} height={tr.h}
                  rx={Math.min(3, w / 2)} data-video={tn.colour ? "" : undefined} />
                {label && (
                  <text className={`bn-tp-clip-label ${teamTurn(tn) ? "on-team" : "on-ppt"}`}
                    style={ink ? { fill: ink } : undefined} x={x0 + 4} y={tr.y + tr.h / 2 + 3.5}>
                    {label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Section flags */}
          {flagOrder.map((i) => {
            const f = s.sections[i];
            const isHot = i === hotFlag;
            const isRaised = i === raised || isHot;
            const fx = x(f.t0);
            const next = i + 1 < s.sections.length ? x(s.sections[i + 1].t0) : xEnd;
            const text = isRaised ? f.label : fit(f.label, next - fx - 20, F.flag);
            const pw = (text ? measure(text, F.flag) : 0) + 12;
            return (
              <g key={`f${i}`} className={`bn-tp-flag${isRaised ? " raised" : ""}${isHot ? " hot" : ""}`}
                onClick={() => onJump(f.t0)}
                onMouseEnter={() => {
                  setHotFlag(i);
                  setPlayhead(f.t0);
                }}
                onMouseLeave={() => {
                  setHotFlag(-1);
                  setPlayhead(null);
                }}>
                <title>{`${f.label} · ${formatTimecode(f.t0)}`}</title>
                <line x1={fx + 0.5} x2={fx + 0.5} y1={2} y2={MT.y - 2} />
                {/* Half-pixel coordinates: a 1px stroke on whole pixels smears across two and
                    reads as a heavier line than the hairline it is. */}
                <path d={`M${fx + 1.5},2.5 h${pw} l-5,7 l5,7 h-${pw} z`}
                  filter={isRaised ? `url(#bn-tp-lift-${s.session_id})` : undefined} />
                {text && <text x={fx + 4} y={13}>{text}</text>}
              </g>
            );
          })}

          {/* Hit area over the speaker lane: hover raises a flag, click jumps to exactly that moment */}
          <rect className="bn-tp-hit" x={TAPESTRY_GUTTER} y={MT.y - 1} width={Math.max(0, xEnd - TAPESTRY_GUTTER)}
            height={PT.y + PT.h - MT.y + 2} fill="transparent"
            onMouseMove={(e) => {
              pendingX.current = e.clientX;
              if (frame.current) return;
              frame.current = requestAnimationFrame(() => {
                frame.current = 0;
                if (pendingX.current === null) return;
                const sec = secAt(pendingX.current);
                setRaised(sectionAt(sec));
                setPlayhead(sec);
              });
            }}
            onMouseLeave={() => {
              pendingX.current = null;
              setRaised(-1);
              setPlayhead(null);
            }}
            onClick={(e) => onJump(secAt(e.clientX))} />
          {playhead !== null && (
            <line className="bn-tp-playhead" x1={x(playhead)} x2={x(playhead)} y1={MT.y - 1} y2={SE.mid + SE.amp} />
          )}

          {/* Sentiment */}
          <line className="bn-tp-axis" x1={TAPESTRY_GUTTER} x2={xEnd} y1={SE.mid} y2={SE.mid} />
          {s.quotes.map((q, i) => {
            const cx = x(q.t0);
            const h = (0.35 + (0.65 * (Math.min(3, Math.max(1, q.intensity)) - 1)) / 2) * SE.amp;
            const dim = (selected >= 0 && i !== selected) || (themeFocus !== null && q.theme !== themeFocus);
            const common = {
              className: `bn-tp-bar${i === selected ? " sel" : ""}${dim ? " dim" : ""}`,
              // One Tab stop per slice (roving): the selected bar, else the first; arrows move.
              tabIndex: (selected >= 0 ? i === selected : i === 0) ? 0 : -1,
              role: "button",
              "aria-expanded": i === selected,
              "aria-controls": panelId,
              "aria-label": [
                q.sentiment ? t(`enums:sentiment.${q.sentiment}`, { defaultValue: q.sentiment }) : "",
                formatTimecode(q.t0),
              ].filter(Boolean).join(" "),
              onClick: () => choose(i),
              onKeyDown: (e: React.KeyboardEvent) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  choose(i);
                } else if (selected < 0 && (e.key === "ArrowRight" || e.key === "ArrowLeft")) {
                  e.preventDefault();
                  choose(Math.max(0, Math.min(s.quotes.length - 1, i + (e.key === "ArrowRight" ? 1 : -1))));
                }
              },
            };
            if (!q.sentiment) {
              return <rect key={i} {...common} className={`${common.className} bn-tp-unrated`} x={cx - 0.75} y={SE.mid - 3} width={1.5} height={6} />;
            }
            const fill = `var(--bn-sentiment-${q.sentiment})`;
            if (q.sentiment === "surprise") return <circle key={i} {...common} cx={cx} cy={SE.mid} r={3.2} style={{ fill }} />;
            return (
              <rect key={i} {...common} style={{ fill }} x={cx - 2} width={4} rx={1} height={h}
                y={POSITIVE.has(q.sentiment) ? SE.mid - h : SE.mid} />
            );
          })}

          {/* Theme spans */}
          {spans.map(([theme, sp]) => {
            const x0 = x(sp.t0);
            const x1 = Math.max(x(sp.t1), x0 + 6);
            const row = themeEnds.indexOf(Math.min(...themeEnds));
            const lx = Math.max(x0, themeEnds[row] + 4);
            const y = TG.y + row * TG.row;
            const text = fit(theme, Math.min(Math.max(x1 - lx, 120), W - RIGHT - lx - 8), F.tag);
            const tw = text ? measure(text, F.tag) : 0;
            themeEnds[row] = Math.max(x1, lx + tw + 8);
            return (
              <g key={theme} className="bn-tp-theme" onMouseEnter={() => setThemeFocus(theme)}
                onMouseLeave={() => setThemeFocus(null)}>
                <title>{theme}</title>
                <rect className="bn-tp-span" x={x0} y={y + 6} width={x1 - x0} height={4} rx={2} />
                {text && (
                  <>
                    <rect className="bn-tp-tag" x={lx} y={y} width={tw + 8} height={16} rx={3} />
                    <text className="bn-tp-tag-text" x={lx + 4} y={y + 12}>{text}</text>
                  </>
                )}
              </g>
            );
          })}

          {ticks.map((tk) => (
            <text key={tk} className={`bn-tp-tick${nearTick === tk ? " near" : ""}`} x={x(tk)} y={H - 2} textAnchor={tk === 0 ? "start" : "middle"}>
              {formatTimecode(tk)}
            </text>
          ))}
        </svg>
      </div>

      {sel && (
        // The whole popover opens the transcript at the quote; the faint hover tint says so.
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <div
          ref={popRef}
          className="bn-tp-popover"
          id={panelId}
          style={{
            left: pop?.left ?? 0,
            top: pop?.top ?? 0,
            width: pop?.width,
            visibility: pop ? "visible" : "hidden",
            "--bn-tp-arrow-x": `${pop?.arrow ?? 24}px`,
            "--bn-tp-accent": sel.sentiment ? `var(--bn-sentiment-${sel.sentiment})` : "var(--bn-colour-border)",
          } as React.CSSProperties}
          onClick={() => onJump(sel.t0)}
        >
          <div className="bn-tp-actions">
            <div className="bn-tp-nav">
              <button type="button" aria-label={t("sessions.tapestry.previousQuote")} disabled={selected <= 0}
                onClick={(e) => {
                  e.stopPropagation();
                  choose(Math.max(0, selected - 1));
                }}>
                <span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5 4 6l3.5 3.5" /></svg></span>
              </button>
              <button type="button" aria-label={t("sessions.tapestry.nextQuote")} disabled={selected >= s.quotes.length - 1}
                onClick={(e) => {
                  e.stopPropagation();
                  choose(Math.min(s.quotes.length - 1, selected + 1));
                }}>
                <span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" /></svg></span>
              </button>
            </div>
            <button type="button" className="bn-tp-close" aria-label={t("buttons.close")}
              onClick={(e) => {
                e.stopPropagation();
                setSelected(-1);
              }}>
              <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M3 3l6 6M9 3l-6 6" /></svg>
            </button>
          </div>
          <div className="bn-tp-meta">
            {sel.sentiment && <Badge text={sel.sentiment} variant="readonly" sentiment={sel.sentiment} />}
            {/* The keyboard way into the transcript; the whole popover is the mouse way. */}
            <button type="button" className="bn-tp-tc" onClick={(e) => {
              e.stopPropagation();
              onJump(sel.t0);
            }}>
              {`${formatTimecode(sel.t0)}–${formatTimecode(sel.t1)}`}
            </button>
            <span>{sel.section ?? sel.theme ?? ""}</span>
          </div>
          <blockquote>{sel.text}</blockquote>
        </div>
      )}
    </div>
  );
}
