/**
 * Tapestry playground — dev-only (`serve --dev`). Nudges every kind of tapestry text up or down
 * the existing type ladder, and the container paddings through short snapped lists, live, then
 * lists the changes to hand back for committing to utils/tapestryTuning.ts.
 *
 * Deliberately cannot invent a size: type moves only between `--bn-text-*` steps, the popover
 * only between `--bn-space-*` steps, and pixel paddings only between the values in PAD_STEPS.
 * Reuses the Responsive Playground's dark panel classes (playground.css).
 */

import { useState } from "react";
import "./playground.css";
import {
  DEFAULTS,
  LADDER,
  PAD_STEPS,
  SPACE,
  type Step,
  type TapestryTuning,
  getTapestryTuning,
  resetTapestryTuning,
  setTapestryTuning,
  tuningChanges,
  useTapestryTuning,
} from "../utils/tapestryTuning";

const TYPE_ROWS: [keyof TapestryTuning["type"], string][] = [
  ["lane", "Lane labels"],
  ["flag", "Section flags"],
  ["clip", "Clip names"],
  ["theme", "Theme tags"],
  ["tick", "Timecodes"],
  ["popMeta", "Popover meta"],
  ["popQuote", "Popover quote"],
];

const PAD_ROWS: [Exclude<keyof TapestryTuning["pad"], "popover">, string][] = [
  ["flagX", "Flag inset"],
  ["flagH", "Flag height"],
  ["clipX", "Clip inset"],
  ["clipH", "Clip height"],
  ["themeX", "Theme inset"],
  ["themeH", "Theme height"],
  ["themeGap", "Theme row gap"],
];

function tokenPx(step: Step): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(`--bn-text-${step}`).trim();
  const n = raw.endsWith("rem") ? parseFloat(raw) * 16 : parseFloat(raw);
  return Number.isFinite(n) ? `${Math.round(n * 10) / 10}px` : "";
}

function move<T>(list: readonly T[], value: T, d: number): T {
  const i = list.indexOf(value);
  return list[Math.max(0, Math.min(list.length - 1, (i < 0 ? 0 : i) + d))];
}

export function TapestryPlayground({ onClose }: { onClose: () => void }) {
  const t = useTapestryTuning();
  const [copied, setCopied] = useState(false);
  const changes = tuningChanges(t);

  const setType = (k: keyof TapestryTuning["type"], d: number) => {
    const cur = getTapestryTuning();
    setTapestryTuning({ ...cur, type: { ...cur.type, [k]: move(LADDER, cur.type[k], d) } });
  };
  const setPad = (k: Exclude<keyof TapestryTuning["pad"], "popover">, d: number) => {
    const cur = getTapestryTuning();
    setTapestryTuning({ ...cur, pad: { ...cur.pad, [k]: move(PAD_STEPS[k], cur.pad[k], d) } });
  };
  const setPopover = (d: number) => {
    const cur = getTapestryTuning();
    setTapestryTuning({ ...cur, pad: { ...cur.pad, popover: move(SPACE, cur.pad.popover, d) } });
  };

  const stepper = (label: string, value: string, changed: boolean, onMove: (d: number) => void, onReset: () => void) => (
    <div className="pg-slider-row" key={label}>
      <span className="pg-slider-label">{label}</span>
      <button type="button" className="pg-btn" aria-label={`${label} smaller`} onClick={() => onMove(-1)}>−</button>
      <span className={`pg-slider-value pg-tp-value${changed ? " pg-overridden" : ""}`}>{value}</span>
      <button type="button" className="pg-btn" aria-label={`${label} larger`} onClick={() => onMove(1)}>+</button>
      <button type="button" className="pg-slider-reset" aria-label={`Reset ${label}`} title="Reset"
        style={{ visibility: changed ? "visible" : "hidden" }} onClick={onReset}>↺</button>
    </div>
  );

  return (
    <div className="pg-float" role="dialog" aria-label="Tapestry playground">
      <div className="pg-header">
        <span className="pg-title">Tapestry playground</span>
        <button type="button" className="pg-btn" onClick={resetTapestryTuning}>Revert All</button>
        <button type="button" className="pg-close" aria-label="Close" onClick={onClose}>&times;</button>
      </div>
      <div className="pg-float-body">
        <div className="pg-section">
          <div className="pg-section-title">Type — along the ladder only</div>
          {TYPE_ROWS.map(([k, label]) =>
            stepper(label, `${t.type[k]} ${tokenPx(t.type[k])}`, t.type[k] !== DEFAULTS.type[k],
              (d) => setType(k, d),
              () => setTapestryTuning({ ...getTapestryTuning(), type: { ...getTapestryTuning().type, [k]: DEFAULTS.type[k] } })),
          )}
        </div>
        <div className="pg-section">
          <div className="pg-section-title">Containers — snapped steps only</div>
          {PAD_ROWS.map(([k, label]) =>
            stepper(label, `${t.pad[k]}px`, t.pad[k] !== DEFAULTS.pad[k],
              (d) => setPad(k, d),
              () => setTapestryTuning({ ...getTapestryTuning(), pad: { ...getTapestryTuning().pad, [k]: DEFAULTS.pad[k] } })),
          )}
          {stepper("Popover padding", `space-${t.pad.popover}`, t.pad.popover !== DEFAULTS.pad.popover,
            setPopover,
            () => setTapestryTuning({ ...getTapestryTuning(), pad: { ...getTapestryTuning().pad, popover: DEFAULTS.pad.popover } }))}
        </div>
        <div className="pg-section">
          <div className="pg-section-title">Changes to commit ({changes.length})</div>
          {changes.length === 0
            ? <div className="pg-tp-none">None — this is the shipped design.</div>
            : <pre className="pg-tp-changes">{changes.join("\n")}</pre>}
          <button type="button" className="pg-btn" disabled={!changes.length} onClick={() => {
            void navigator.clipboard?.writeText(changes.join("\n")).then(() => {
              setCopied(true);
              setTimeout(() => setCopied(false), 1500);
            });
          }}>{copied ? "Copied" : "Copy changes"}</button>
        </div>
      </div>
    </div>
  );
}
