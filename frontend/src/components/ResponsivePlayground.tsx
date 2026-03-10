/**
 * ResponsivePlayground — dev-only bottom drawer for interactive
 * responsive layout experimentation.
 *
 * Three sections arranged horizontally:
 * 1. Breakpoint sets + Device presets
 * 2. Token tuner (sliders for layout + type tokens)
 * 3. Visual aids (grid overlay, baseline grid, dark mode, density)
 *
 * Plus collapsible TypeScalePreview.
 */

import "./playground.css";
import { useCallback, useRef } from "react";
import {
  usePlaygroundStore,
  TOKEN_DEFAULTS,
  togglePlayground,
  setTargetWidth,
  setQuoteMaxWidth,
  setGridGap,
  setMaxWidth,
  setSpacingScale,
  setRadiusScale,
  setBaseFontSize,
  setTypeScaleRatio,
  setLineHeight,
  setBreakpointSet,
  toggleGridOverlay,
  toggleBaselineGrid,
  setBaselineUnit,
  setDarkMode,
  setTypeScalePreset,
  setRailWidth,
  setMinimapWidth,
  setGutterLeft,
  setGutterRight,
  setOverlayDuration,
  setHoverDelay,
  setLeaveGrace,
  resetPlayground,
} from "../contexts/PlaygroundStore";
import {
  DEVICE_PRESETS,
  BREAKPOINT_SETS,
} from "../data/devicePresets";
import {
  ALL_TYPE_SCALE_PRESETS,
} from "../data/typeScalePresets";
import { TypeScalePreview } from "./TypeScalePreview";
import { PlaygroundFab } from "./PlaygroundFab";

// ── Slider helper ─────────────────────────────────────────────────────────

function TokenSlider({
  label,
  value,
  defaultValue,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string;
  value: number | null;
  defaultValue: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number | null) => void;
}) {
  const current = value ?? defaultValue;
  const isOverridden = value !== null;
  return (
    <div className="pg-slider-row">
      <label className="pg-slider-label">{label}</label>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={current}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="pg-slider"
      />
      <span className={`pg-slider-value${isOverridden ? " pg-overridden" : ""}`}>
        {current.toFixed(step < 1 ? (step < 0.1 ? 2 : 1) : 0)}
        {unit}
      </span>
      {isOverridden && (
        <button
          className="pg-slider-reset"
          onClick={() => onChange(null)}
          title="Reset to default"
          type="button"
        >
          &times;
        </button>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────

export function ResponsivePlayground() {
  const pg = usePlaygroundStore();
  const drawerRef = useRef<HTMLDivElement>(null);
  const dragStartY = useRef(0);
  const dragStartH = useRef(0);

  // Drag-to-resize top edge
  const handleDragStart = useCallback(
    (e: React.PointerEvent) => {
      e.preventDefault();
      dragStartY.current = e.clientY;
      dragStartH.current = pg.drawerHeight;
      const onMove = (ev: PointerEvent) => {
        const delta = dragStartY.current - ev.clientY;
        const newH = Math.max(100, Math.min(600, dragStartH.current + delta));
        if (drawerRef.current) {
          drawerRef.current.style.height = `${newH}px`;
        }
      };
      const onUp = (ev: PointerEvent) => {
        document.removeEventListener("pointermove", onMove);
        document.removeEventListener("pointerup", onUp);
        const delta = dragStartY.current - ev.clientY;
        const newH = Math.max(100, Math.min(600, dragStartH.current + delta));
        // Persist via store
        import("../contexts/PlaygroundStore").then((mod) =>
          mod.setDrawerHeight(newH),
        );
      };
      document.addEventListener("pointermove", onMove);
      document.addEventListener("pointerup", onUp);
    },
    [pg.drawerHeight],
  );

  if (!pg.open) return <PlaygroundFab />;

  return (
    <div
      ref={drawerRef}
      className="pg-drawer"
      style={{ height: pg.drawerHeight }}
    >
      {/* Drag handle */}
      <div className="pg-drag-handle" onPointerDown={handleDragStart}>
        <div className="pg-drag-grip" />
      </div>

      {/* Header */}
      <div className="pg-header">
        <span className="pg-title">Responsive Playground</span>
        <button
          className="pg-btn"
          onClick={resetPlayground}
          title="Revert all overrides"
          type="button"
        >
          Revert All
        </button>
        <button
          className="pg-close"
          onClick={togglePlayground}
          title="Close (Ctrl+Shift+R)"
          type="button"
        >
          &times;
        </button>
      </div>

      {/* Three-column body */}
      <div className="pg-body">
        {/* Column 1: Breakpoints + Devices */}
        <div className="pg-col">
          <div className="pg-section">
            <div className="pg-section-title">Breakpoint Sets</div>
            <select
              className="pg-select"
              value={pg.breakpointSet}
              onChange={(e) => setBreakpointSet(e.target.value)}
            >
              {Object.entries(BREAKPOINT_SETS).map(([key, bp]) => (
                <option key={key} value={key}>
                  {bp.name} — {bp.source}
                </option>
              ))}
            </select>
            <div className="pg-bp-values">
              {BREAKPOINT_SETS[pg.breakpointSet]?.values.map((v) => (
                <span key={v} className="pg-bp-chip">
                  {v}
                </span>
              ))}
            </div>
          </div>

          <div className="pg-section">
            <div className="pg-section-title">Device Presets</div>
            <div className="pg-device-grid">
              {DEVICE_PRESETS.map((d) => (
                <button
                  key={d.name}
                  className={`pg-device-btn${pg.targetWidth === d.width ? " pg-active" : ""}`}
                  onClick={() => setTargetWidth(d.width)}
                  title={d.width ? `${d.width}px` : "Full width"}
                  type="button"
                >
                  <span className="pg-device-name">{d.name}</span>
                  {d.width && (
                    <span className="pg-device-width">{d.width}</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Column 2: Token Tuner */}
        <div className="pg-col">
          <div className="pg-section">
            <div className="pg-section-title">Layout Tokens</div>
            <TokenSlider
              label="Quote max width"
              value={pg.quoteMaxWidth}
              defaultValue={TOKEN_DEFAULTS.quoteMaxWidth}
              min={16}
              max={44}
              step={0.5}
              unit="rem"
              onChange={setQuoteMaxWidth}
            />
            <TokenSlider
              label="Grid gap"
              value={pg.gridGap}
              defaultValue={TOKEN_DEFAULTS.gridGap}
              min={0}
              max={3}
              step={0.25}
              unit="rem"
              onChange={setGridGap}
            />
            <TokenSlider
              label="Article max width"
              value={pg.maxWidth}
              defaultValue={TOKEN_DEFAULTS.maxWidth}
              min={32}
              max={100}
              step={2}
              unit="rem"
              onChange={setMaxWidth}
            />
            <TokenSlider
              label="Spacing scale"
              value={pg.spacingScale}
              defaultValue={TOKEN_DEFAULTS.spacingScale}
              min={0.5}
              max={2}
              step={0.1}
              unit="x"
              onChange={setSpacingScale}
            />
            <TokenSlider
              label="Radius scale"
              value={pg.radiusScale}
              defaultValue={TOKEN_DEFAULTS.radiusScale}
              min={0}
              max={3}
              step={0.25}
              unit="x"
              onChange={setRadiusScale}
            />
          </div>

          <div className="pg-section">
            <div className="pg-section-title">Sidebar Layout</div>
            <TokenSlider
              label="Rail width"
              value={pg.railWidth}
              defaultValue={TOKEN_DEFAULTS.railWidth}
              min={24}
              max={64}
              step={2}
              unit="px"
              onChange={setRailWidth}
            />
            <TokenSlider
              label="Minimap width"
              value={pg.minimapWidth}
              defaultValue={TOKEN_DEFAULTS.minimapWidth}
              min={0}
              max={96}
              step={4}
              unit="px"
              onChange={setMinimapWidth}
            />
            <TokenSlider
              label="Left gutter"
              value={pg.gutterLeft}
              defaultValue={TOKEN_DEFAULTS.gutterLeft}
              min={0}
              max={64}
              step={4}
              unit="px"
              onChange={setGutterLeft}
            />
            <TokenSlider
              label="Right gutter"
              value={pg.gutterRight}
              defaultValue={TOKEN_DEFAULTS.gutterRight}
              min={0}
              max={80}
              step={4}
              unit="px"
              onChange={setGutterRight}
            />
            <TokenSlider
              label="Overlay speed"
              value={pg.overlayDuration}
              defaultValue={TOKEN_DEFAULTS.overlayDuration}
              min={0.1}
              max={1.0}
              step={0.05}
              unit="s"
              onChange={setOverlayDuration}
            />
            <TokenSlider
              label="Hover delay"
              value={pg.hoverDelay}
              defaultValue={TOKEN_DEFAULTS.hoverDelay}
              min={100}
              max={1000}
              step={50}
              unit="ms"
              onChange={setHoverDelay}
            />
            <TokenSlider
              label="Leave grace"
              value={pg.leaveGrace}
              defaultValue={TOKEN_DEFAULTS.leaveGrace}
              min={0}
              max={500}
              step={25}
              unit="ms"
              onChange={setLeaveGrace}
            />
          </div>

          <div className="pg-section">
            <div className="pg-section-title">Type Scale</div>
            <select
              className="pg-select"
              value={pg.typeScalePreset ?? ""}
              onChange={(e) => {
                const name = e.target.value || null;
                setTypeScalePreset(name);
                if (name) {
                  const preset = ALL_TYPE_SCALE_PRESETS.find(
                    (p) => p.name === name,
                  );
                  if (preset?.ratio) {
                    setTypeScaleRatio(preset.ratio);
                    if (preset.base) setBaseFontSize(preset.base);
                  }
                }
              }}
            >
              <option value="">Custom</option>
              <optgroup label="Musical Ratios">
                {ALL_TYPE_SCALE_PRESETS.filter(
                  (p) => p.origin === "Musical",
                ).map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                    {p.ratio ? ` (${p.ratio})` : ""}
                  </option>
                ))}
              </optgroup>
              <optgroup label="Design Systems">
                {ALL_TYPE_SCALE_PRESETS.filter(
                  (p) => p.origin === "Design System",
                ).map((p) => (
                  <option key={p.name} value={p.name}>
                    {p.name}
                    {p.base ? ` (base ${p.base}px)` : ""}
                  </option>
                ))}
              </optgroup>
            </select>
            <TokenSlider
              label="Base font size"
              value={pg.baseFontSize}
              defaultValue={TOKEN_DEFAULTS.baseFontSize}
              min={12}
              max={22}
              step={1}
              unit="px"
              onChange={setBaseFontSize}
            />
            <TokenSlider
              label="Scale ratio"
              value={pg.typeScaleRatio}
              defaultValue={TOKEN_DEFAULTS.typeScaleRatio}
              min={1.067}
              max={1.618}
              step={0.01}
              unit=""
              onChange={setTypeScaleRatio}
            />
            <TokenSlider
              label="Line height"
              value={pg.lineHeight}
              defaultValue={TOKEN_DEFAULTS.lineHeight}
              min={1.2}
              max={2.0}
              step={0.05}
              unit=""
              onChange={setLineHeight}
            />
          </div>
        </div>

        {/* Column 3: Visual Aids */}
        <div className="pg-col">
          <div className="pg-section">
            <div className="pg-section-title">Visual Aids</div>

            <label className="pg-toggle-row">
              <input
                type="checkbox"
                checked={pg.gridOverlay}
                onChange={toggleGridOverlay}
              />
              <span>Column grid overlay</span>
            </label>

            <label className="pg-toggle-row">
              <input
                type="checkbox"
                checked={pg.baselineGrid}
                onChange={toggleBaselineGrid}
              />
              <span>Baseline grid</span>
            </label>

            {pg.baselineGrid && (
              <div className="pg-baseline-units">
                {[2, 4, 6, 8, 12].map((u) => (
                  <button
                    key={u}
                    className={`pg-bp-chip${pg.baselineUnit === u ? " pg-active" : ""}`}
                    onClick={() => setBaselineUnit(u)}
                    type="button"
                  >
                    {u}px
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="pg-section">
            <div className="pg-section-title">Theme</div>
            <div className="pg-theme-btns">
              <button
                className={`pg-btn${pg.darkMode === null ? " pg-active" : ""}`}
                onClick={() => setDarkMode(null)}
                type="button"
              >
                Auto
              </button>
              <button
                className={`pg-btn${pg.darkMode === "light" ? " pg-active" : ""}`}
                onClick={() => setDarkMode("light")}
                type="button"
              >
                Light
              </button>
              <button
                className={`pg-btn${pg.darkMode === "dark" ? " pg-active" : ""}`}
                onClick={() => setDarkMode("dark")}
                type="button"
              >
                Dark
              </button>
            </div>
          </div>

          <div className="pg-section">
            <div className="pg-section-title">Density</div>
            <div className="pg-theme-btns">
              {[
                { label: "Compact", size: 14 },
                { label: "Normal", size: 16 },
                { label: "Generous", size: 18 },
              ].map((d) => (
                <button
                  key={d.label}
                  className={`pg-btn${(pg.baseFontSize ?? 16) === d.size ? " pg-active" : ""}`}
                  onClick={() =>
                    setBaseFontSize(d.size === 16 ? null : d.size)
                  }
                  type="button"
                >
                  {d.label}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Type scale preview (full width, collapsible) */}
      <TypeScalePreview />
    </div>
  );
}
