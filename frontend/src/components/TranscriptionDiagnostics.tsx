/**
 * TranscriptionDiagnostics — how Whisper heard one recording, under its session timeline.
 *
 * Shown only when the researcher's diagnostics preference is on (the Mac's Diagnostics
 * preference injects `__BRISTLENOSE_DIAGNOSTICS__`; `serve --dev` shows it too), so it is
 * diagnostic chrome and stays English (docs/design-i18n.md, "Which surfaces are targets").
 *
 * Rendered inside the timeline's own scroll container: the four lanes share its time scale
 * and scroll with it, while the header and panels stay put (`position: sticky`). Numbers
 * only — none of them knows what was said, so none is an accuracy score
 * (docs/design-transcription-quality.md). No flag sentences yet: their thresholds are
 * still to be measured on real projects.
 */

import { useId, useState } from "react";
import { TAPESTRY_GUTTER, TAPESTRY_RIGHT } from "../utils/tapestryScale";
import { formatTimecode } from "../utils/format";

/** One session's record, as `bristlenose/transcription_quality.py` writes it (version 1). */
export interface TranscriptionQuality {
  version: number;
  session_id: string;
  duration_s: number;
  audio: {
    floor_dbfs: number | null;
    peak_dbfs: number | null;
    active_share: number;
    clipped_share: number;
  } | null;
  recognition: {
    backend?: string;
    model?: string;
    transcribed?: boolean;
    language?: string | null;
    language_set?: boolean;
    prompt?: boolean;
    decode_windows?: number;
    /** Null when mlx did not report window temperatures: unknown, not zero. */
    fallback_windows?: number | null;
    mean_confidence: number | null;
    low_confidence_share: number | null;
  };
  repair: {
    silent_dropped?: number;
    echoes_dropped?: number;
    loop_segments_removed?: number;
    skipped_found?: number;
    skipped_seconds?: number;
    skipped_recovered?: number;
    recovered_words?: number;
    found?: [number, number][];
    still_empty?: [number, number][];
    inaudible_gaps: number;
    inaudible_seconds: number;
  };
  text: {
    words: number;
    wpm: number;
    sentence_ends_per_100: number;
    longest_unpunctuated: number;
  };
  series: {
    bin_s: number;
    level_p90: (number | null)[];
    wpm: number[];
    low_conf: (number | null)[];
  };
}

interface Props {
  record: TranscriptionQuality;
  /** The timeline's duration and scale, so the lanes line up with it. */
  durationSeconds: number;
  sPerPx: number;
  onJump: (seconds: number) => void;
}

const LANE_H = 18;
const LANE_GAP = 5;
type Lane = "Sound" | "Pace" | "Doubt" | "Gaps";

const pct = (n: number, digits = 0) => `${(100 * n).toFixed(digits)}%`;
const spanSeconds = (spans: [number, number][] | undefined) =>
  (spans ?? []).reduce((sum, [a, b]) => sum + (b - a), 0);

/** The two numbers that separated the worst recording from the rest in the trials. */
export function headline(r: TranscriptionQuality): string {
  if (r.recognition.transcribed === false) return "Not transcribed: no sound above the floor";
  const parts: string[] = [];
  const windows = r.recognition.decode_windows ?? 0;
  const retried = r.recognition.fallback_windows;
  if (windows > 0 && retried != null) parts.push(`${pct(retried / windows)} of windows retried`);
  if (r.repair.still_empty !== undefined) {
    const empty = spanSeconds(r.repair.still_empty);
    parts.push(empty > 0 ? `${formatTimecode(empty)} with sound but no words` : "no stretch with sound and no words found");
  }
  if (r.repair.inaudible_gaps > 0) {
    parts.push(`${r.repair.inaudible_gaps} inaudible (${formatTimecode(r.repair.inaudible_seconds)})`);
  }
  return parts.join(" · ");
}

export default function TranscriptionDiagnostics({ record: r, durationSeconds, sPerPx, onJump }: Props) {
  const [open, setOpen] = useState(false);
  const panelId = useId();
  const x = (sec: number) => TAPESTRY_GUTTER + sec / sPerPx;
  const duration = Math.max(durationSeconds, r.duration_s);
  const W = Math.ceil(x(duration) + TAPESTRY_RIGHT);
  const y = (i: number) => 4 + i * (LANE_H + LANE_GAP);
  // A lane with nothing measured is left out, so it never reads as silence or as no gaps.
  const lanes: Lane[] = [
    ...(r.series.level_p90.some((v) => v !== null) ? ["Sound" as const] : []),
    "Pace",
    "Doubt",
    ...(r.repair.found !== undefined ? ["Gaps" as const] : []),
  ];
  const row = (lane: Lane) => y(lanes.indexOf(lane));
  const H = y(lanes.length);
  const bin = r.series.bin_s || 10;
  const bw = Math.max(0.5, bin / sPerPx);

  // Sound: the loudest tenth of each bin, on a -70..0 dBFS scale; the noise floor dashed.
  const yLevel = (v: number) => row("Sound") + LANE_H - LANE_H * Math.max(0, Math.min(1, (v + 70) / 70));
  const soundPath = r.series.level_p90
    .map((v, i) => (v === null ? null : `${x(i * bin + bin / 2).toFixed(1)},${yLevel(v).toFixed(1)}`))
    .filter(Boolean)
    .join(" ");
  const floor = r.audio?.floor_dbfs;

  const rec = r.recognition;
  const rep = r.repair;
  const windows = rec.decode_windows ?? 0;

  return (
    // As wide as the lanes, so the header and panels have room to stay put while they scroll.
    <div className="bn-dx" style={{ width: W }}>
      <div className="bn-dx-head">
        <button
          type="button"
          className="bn-dx-toggle"
          aria-expanded={open}
          aria-controls={panelId}
          onClick={() => setOpen((o) => !o)}
        >
          <span className="bn-dx-chevron" aria-hidden="true">{open ? "▾" : "▸"}</span>
          Diagnostics
        </button>
        <span className="bn-dx-headline">{headline(r)}</span>
      </div>

      {open && (
        <div id={panelId}>
          <svg className="bn-dx-lanes" width={W} height={H} viewBox={`0 0 ${W} ${H}`}
            role="img" aria-label="Sound level, words a minute, doubtful words and gaps over time">
            {lanes.map((name, i) => (
              <text key={name} className="bn-tp-lane" x={12} y={y(i) + LANE_H / 2 + 4}>{name}</text>
            ))}
            {lanes.map((name, i) => (
              <rect key={name} className="bn-dx-track" x={TAPESTRY_GUTTER} y={y(i)}
                width={Math.max(0, x(duration) - TAPESTRY_GUTTER)} height={LANE_H} rx={3} />
            ))}

            {lanes.includes("Sound") && floor != null && (
              <line className="bn-dx-floor" x1={TAPESTRY_GUTTER} x2={x(duration)}
                y1={yLevel(floor)} y2={yLevel(floor)} />
            )}
            {lanes.includes("Sound") && soundPath && <polyline className="bn-dx-sound" points={soundPath} />}

            {r.series.wpm.map((v, i) => {
              const h = Math.min(LANE_H, (LANE_H * v) / 240);
              return h > 0 ? (
                <rect key={i} className="bn-dx-pace" x={x(i * bin)} y={row("Pace") + LANE_H - h}
                  width={Math.max(0.5, bw - 0.5)} height={h} />
              ) : null;
            })}

            {r.series.low_conf.map((v, i) =>
              v === null ? null : (
                <rect key={i} className="bn-dx-doubt" x={x(i * bin)} y={row("Doubt")}
                  width={Math.max(0.5, bw - 0.5)} height={LANE_H} style={{ opacity: Math.min(1, v * 1.5) }} />
              ),
            )}

            {lanes.includes("Gaps") && (rep.found ?? []).map(([a, b]) => (
              <rect key={`f${a}`} className="bn-dx-gap-found" x={x(a)} y={row("Gaps") + 1}
                width={Math.max(1, (b - a) / sPerPx)} height={LANE_H - 2} />
            ))}
            {lanes.includes("Gaps") && (rep.still_empty ?? []).map(([a, b]) => (
              <rect key={`e${a}`} className="bn-dx-gap-empty" x={x(a)} y={row("Gaps") + 1}
                width={Math.max(1, (b - a) / sPerPx)} height={LANE_H - 2} onClick={() => onJump(a)}>
                <title>{`${formatTimecode(a)}–${formatTimecode(b)}: sound, no words`}</title>
              </rect>
            ))}
          </svg>

          <div className="bn-dx-panels">
            {r.audio && (
              <Panel title="Audio" rows={[
                ["Noise floor", r.audio.floor_dbfs == null ? "—" : `${r.audio.floor_dbfs} dBFS`],
                ["Peak", r.audio.peak_dbfs == null ? "—" : `${r.audio.peak_dbfs} dBFS`],
                ["Sound", pct(r.audio.active_share), `of ${formatTimecode(r.duration_s)}`],
                ["Clipped", pct(r.audio.clipped_share, 2)],
              ]} />
            )}
            <Panel title="Recognition" rows={[
              ["Engine", [rec.backend, rec.model].filter(Boolean).join(" · ") || "—"],
              ["Language", rec.language ?? "—", rec.language ? (rec.language_set ? "set" : "detected") : undefined],
              ["Style prompt", rec.prompt ? "on" : "off"],
              ...(windows > 0 ? [
                ["Windows", String(windows)],
                rec.fallback_windows == null
                  ? ["Retried", "—", "not reported"]
                  : ["Retried", String(rec.fallback_windows), pct(rec.fallback_windows / windows)],
              ] as Row[] : []),
              ["Confidence", rec.mean_confidence == null ? "—" : rec.mean_confidence.toFixed(2), "mean"],
              ["Doubtful", rec.low_confidence_share == null ? "—" : pct(rec.low_confidence_share), "under 0.5"],
            ]} />
            <Panel title="Repair" rows={[
              ...(rep.skipped_found !== undefined ? [
                ["Sound, no words", String(rep.skipped_found), `${formatTimecode(rep.skipped_seconds ?? 0)}`],
                ["Recovered", String(rep.skipped_recovered ?? 0), `${rep.recovered_words ?? 0} words`],
              ] as Row[] : []),
              ["Inaudible", String(rep.inaudible_gaps), formatTimecode(rep.inaudible_seconds)],
              ...(rep.loop_segments_removed !== undefined ? [
                ["Loop lines removed", String(rep.loop_segments_removed)],
                ["Prompt echoes", String(rep.echoes_dropped ?? 0)],
                ["Silent lines", String(rep.silent_dropped ?? 0)],
              ] as Row[] : []),
            ]}>
              {(rep.still_empty ?? []).length > 0 && (
                <p className="bn-dx-listen">
                  Listen at{" "}
                  {(rep.still_empty ?? []).map(([a], i) => (
                    <span key={a}>
                      {i > 0 && ", "}
                      <button type="button" className="bn-dx-time" onClick={() => onJump(a)}>
                        {formatTimecode(a)}
                      </button>
                    </span>
                  ))}
                </p>
              )}
            </Panel>
            <Panel title="Text" rows={[
              ["Words", String(r.text.words)],
              ["Pace", String(r.text.wpm), "a minute"],
              ["Sentence ends", String(r.text.sentence_ends_per_100), "per 100 words"],
              ["No punctuation", String(r.text.longest_unpunctuated), "words, longest run"],
            ]} />
          </div>
        </div>
      )}
    </div>
  );
}

type Row = [string, string] | [string, string, string | undefined];

function Panel({ title, rows, children }: { title: string; rows: Row[]; children?: React.ReactNode }) {
  return (
    <section className="bn-dx-panel" aria-label={title}>
      <h4 className="bn-dx-panel-title">{title}</h4>
      <dl className="bn-dx-kv">
        {rows.map(([k, v, note]) => (
          <div key={k} className="bn-dx-row">
            <dt>{k}</dt>
            <dd>{v}{note ? <span className="bn-dx-note"> {note}</span> : null}</dd>
          </div>
        ))}
      </dl>
      {children}
    </section>
  );
}
