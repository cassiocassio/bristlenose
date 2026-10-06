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

import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "./Badge";
import type { TapestryQuote, TapestrySession } from "../utils/types";
import { TAPESTRY_GUTTER, TAPESTRY_RIGHT as RIGHT } from "../utils/tapestryScale";
import { formatTimecode } from "../utils/format";

/** Clips are drawn as rounded clips at or below this many seconds per pixel, as slivers above it. */
const CLIP_THRESHOLD = 2.5;
const POSITIVE = new Set(["satisfaction", "delight", "confidence"]);

// ── Text fitting: measured with the fonts the SVG classes render in ───────
let measureCtx: CanvasRenderingContext2D | null | undefined;
function measure(text: string, font: string): number {
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
function fonts(): { flag: string; tag: string; clip: string } {
  const cs = getComputedStyle(document.documentElement);
  const v = (n: string, fallback: string) => cs.getPropertyValue(n).trim() || fallback;
  const px = (val: string) => (val.endsWith("rem") ? `${parseFloat(val) * 16}px` : val);
  const body = v("--bn-font-body", "system-ui, sans-serif");
  const mono = v("--bn-font-mono", "ui-monospace, monospace");
  return {
    flag: `${v("--bn-weight-emphasis", "490")} ${px(v("--bn-text-badge", "11.5px"))} ${body}`,
    tag: `${v("--bn-weight-light", "370")} ${px(v("--bn-text-micro", "9.6px"))} ${mono}`,
    clip: `${v("--bn-weight-emphasis", "490")} ${px(v("--bn-text-micro", "9.6px"))} ${body}`,
  };
}

const isTeam = (code: string) => /^[mo]/.test(code);
function luminance(hex: string): number {
  const n = parseInt(hex.slice(1), 16);
  return 0.299 * ((n >> 16) & 255) + 0.587 * ((n >> 8) & 255) + 0.114 * (n & 255);
}

interface Props {
  session: TapestrySession;
  sPerPx: number;
  /** Display name for a slot code; falls back to the code. */
  nameOf: (slot: string) => string;
  onJump: (seconds: number) => void;
}

export default function SessionTapestry({ session, sPerPx, nameOf, onJump }: Props) {
  const { t } = useTranslation();
  const svgRef = useRef<SVGSVGElement>(null);
  const [raised, setRaised] = useState(-1);
  const [playhead, setPlayhead] = useState<number | null>(null);
  const [selected, setSelected] = useState(-1);
  const [themeFocus, setThemeFocus] = useState<string | null>(null);
  const F = useMemo(() => fonts(), []);

  const s = session;
  const x = (sec: number) => TAPESTRY_GUTTER + sec / sPerPx;
  const xEnd = x(s.duration_seconds);
  const W = Math.ceil(xEnd + RIGHT);
  const clips = sPerPx <= CLIP_THRESHOLD;
  const MT = { y: 26, h: 16 };
  const PT = { y: 45, h: 18 };
  const SE = { mid: 104, amp: 30 };
  const TG = { y: 144, row: 17, rows: 3 };
  const H = TG.y + TG.row * TG.rows + 14;

  // While a quote is open, ← → step quotes and Esc closes, whatever has focus:
  // WebKit does not focus an SVG element on click, so a bar-scoped handler let
  // the arrow fall through to the slice's horizontal scroll.
  useEffect(() => {
    if (selected < 0) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.metaKey || e.altKey || e.ctrlKey) return;
      const tgt = e.target as HTMLElement | null;
      if (tgt?.closest?.("input, textarea, select, [contenteditable='true']")) return;
      if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
        e.preventDefault();
        setSelected((i) => Math.max(0, Math.min(s.quotes.length - 1, i + (e.key === "ArrowRight" ? 1 : -1))));
      } else if (e.key === "Escape") {
        e.preventDefault();
        setSelected(-1);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [selected, s.quotes.length]);

  // Keep the selected bar in view inside the horizontally scrolling slice.
  useEffect(() => {
    if (selected < 0) return;
    const wrap = svgRef.current?.parentElement;
    const q = s.quotes[selected];
    if (!wrap || !q) return;
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

  const tickStep = [60, 120, 300, 600, 900, 1800].find((st) => st / sPerPx >= 64) ?? 3600;
  const ticks: number[] = [];
  for (let tk = 0; tk <= s.duration_seconds; tk += tickStep) ticks.push(tk);

  const flagOrder = s.sections.map((_, i) => i).filter((i) => i !== raised);
  if (raised >= 0) flagOrder.push(raised); // raised flag draws last, on top

  const themeEnds = Array(TG.rows).fill(-1e9) as number[];
  const sel: TapestryQuote | undefined = selected >= 0 ? s.quotes[selected] : undefined;

  return (
    <>
      <div className="bn-tapestry-scroll">
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
          <text className="bn-tp-lane" x={8} y={14}>{t("quotes.sections")}</text>
          <text className="bn-tp-lane" x={8} y={MT.y + 12}>{t("sessions.speakerPlaceholder.moderator")}</text>
          <text className="bn-tp-lane" x={8} y={PT.y + 13}>{t("sessions.speakerPlaceholder.participant")}</text>
          <text className="bn-tp-lane" x={8} y={SE.mid + 3}>{t("sessions.colSentiment")}</text>
          <text className="bn-tp-lane" x={8} y={TG.y + 11}>{t("quotes.themes")}</text>

          {/* Speaker clips */}
          <rect className="bn-tp-track" x={TAPESTRY_GUTTER} y={MT.y - 1} width={Math.max(0, xEnd - TAPESTRY_GUTTER)}
            height={PT.y + PT.h - MT.y + 2} rx={4} />
          {s.turns.map((tn, i) => {
            const tr = isTeam(tn.speaker) ? MT : PT;
            const x0 = x(tn.t0);
            const w = x(tn.t1) - x0;
            const cls = `bn-tp-clip ${isTeam(tn.speaker) ? "bn-tp-clip-team" : "bn-tp-clip-ppt"}`;
            const style = tn.colour ? { fill: tn.colour } : undefined;
            if (!clips) {
              return <rect key={i} className={cls} style={style} x={x0} y={tr.y} width={Math.max(0.5, w)} height={tr.h} />;
            }
            if (w < 1) return null;
            const label = fit(nameOf(tn.speaker), w - 8, F.clip) || (w > 22 ? tn.speaker : "");
            const dark = tn.colour ? luminance(tn.colour) <= 150 : !isTeam(tn.speaker);
            return (
              <g key={i}>
                <rect className={cls} style={style} x={x0 + 0.5} y={tr.y} width={Math.max(1, w - 1)} height={tr.h}
                  rx={Math.min(3, w / 2)} data-video={tn.colour ? "" : undefined} />
                {label && (
                  <text className={`bn-tp-clip-label${dark ? " on-dark" : ""}`} x={x0 + 4} y={tr.y + tr.h / 2 + 3.5}>
                    {label}
                  </text>
                )}
              </g>
            );
          })}

          {/* Section flags */}
          {flagOrder.map((i) => {
            const f = s.sections[i];
            const isRaised = i === raised;
            const fx = x(f.t0);
            const next = i + 1 < s.sections.length ? x(s.sections[i + 1].t0) : xEnd;
            const text = isRaised ? f.label : fit(f.label, next - fx - 20, F.flag);
            const pw = (text ? measure(text, F.flag) : 0) + 12;
            return (
              <g key={`f${i}`} className={`bn-tp-flag${isRaised ? " raised" : ""}`}
                onClick={() => onJump(f.t0)}>
                <title>{`${f.label} · ${formatTimecode(f.t0)}`}</title>
                <line x1={fx + 0.5} x2={fx + 0.5} y1={2} y2={MT.y - 2} />
                <path d={`M${fx + 1},2 h${pw} l-5,7 l5,7 h-${pw} z`}
                  filter={isRaised ? `url(#bn-tp-lift-${s.session_id})` : undefined} />
                {text && <text x={fx + 4} y={13}>{text}</text>}
              </g>
            );
          })}

          {/* Hit area over the speaker lane: hover raises a flag, click jumps to exactly that moment */}
          <rect className="bn-tp-hit" x={TAPESTRY_GUTTER} y={MT.y - 1} width={Math.max(0, xEnd - TAPESTRY_GUTTER)}
            height={PT.y + PT.h - MT.y + 2} fill="transparent"
            onMouseMove={(e) => {
              const sec = secAt(e.clientX);
              setRaised(sectionAt(sec));
              setPlayhead(sec);
            }}
            onMouseLeave={() => {
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
              tabIndex: 0,
              role: "button",
              "aria-label": `${q.sentiment ? t(`enums:sentiment.${q.sentiment}`, { defaultValue: q.sentiment }) : "—"} ${formatTimecode(q.t0)}`,
              onClick: () => setSelected(i),
              onKeyDown: (e: React.KeyboardEvent) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelected(i);
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
                <rect className="bn-tp-span" x={x0} y={y + 5} width={x1 - x0} height={4} rx={2} />
                {text && (
                  <>
                    <rect className="bn-tp-tag" x={lx} y={y} width={tw + 8} height={14} rx={3} />
                    <text className="bn-tp-tag-text" x={lx + 4} y={y + 10.5}>{text}</text>
                  </>
                )}
              </g>
            );
          })}

          {ticks.map((tk) => (
            <text key={tk} className="bn-tp-tick" x={x(tk)} y={H - 2} textAnchor={tk === 0 ? "start" : "middle"}>
              {formatTimecode(tk)}
            </text>
          ))}
        </svg>
      </div>

      {sel && (
        // The whole panel opens the transcript at the quote; the faint hover tint says so.
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <div
          className="bn-tp-card"
          style={{ "--bn-tp-accent": sel.sentiment ? `var(--bn-sentiment-${sel.sentiment})` : "var(--bn-colour-border)" } as React.CSSProperties}
          onClick={() => onJump(sel.t0)}
          aria-live="polite"
        >
          <div className="bn-tp-nav">
            <button type="button" aria-label={t("sessions.tapestry.previousQuote")} disabled={selected <= 0}
              onClick={(e) => {
                e.stopPropagation();
                setSelected((i) => Math.max(0, i - 1));
              }}>
              <span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M7.5 2.5 4 6l3.5 3.5" /></svg></span>
            </button>
            <button type="button" aria-label={t("sessions.tapestry.nextQuote")} disabled={selected >= s.quotes.length - 1}
              onClick={(e) => {
                e.stopPropagation();
                setSelected((i) => Math.min(s.quotes.length - 1, i + 1));
              }}>
              <span><svg viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 2.5 8 6l-3.5 3.5" /></svg></span>
            </button>
          </div>
          <div className="bn-tp-meta">
            {sel.sentiment && <Badge text={sel.sentiment} variant="readonly" sentiment={sel.sentiment} />}
            <span className="bn-tp-tc">{`${formatTimecode(sel.t0)}–${formatTimecode(sel.t1)}`}</span>
            <span>{sel.section ?? sel.theme ?? ""}</span>
          </div>
          <blockquote>{sel.text}</blockquote>
        </div>
      )}
    </>
  );
}
