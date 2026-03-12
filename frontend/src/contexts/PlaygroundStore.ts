/**
 * PlaygroundStore — module-level store for the responsive design playground.
 *
 * Dev-only. Uses the same pattern as SidebarStore: plain module-level state
 * object + useSyncExternalStore. Persists to sessionStorage (not localStorage)
 * so playground state doesn't survive tab close.
 *
 * Manages: panel open/close, HUD visibility, viewport simulation, CSS token
 * overrides, type scale, grid overlays. All CSS changes are injected via a
 * single <style id="bn-playground-overrides"> element.
 *
 * @module PlaygroundStore
 */

import { useSyncExternalStore } from "react";

// ── Constants ─────────────────────────────────────────────────────────────

const SS_KEY = "bn-playground";

/** Default token values (must match tokens.css) */
export const TOKEN_DEFAULTS = {
  quoteMaxWidth: 23, // rem
  gridGap: 1.25, // rem
  maxWidth: 52, // rem
  spacingScale: 1.0,
  radiusScale: 1.0,
  baseFontSize: 16, // px
  typeScaleRatio: 1.25, // Major Third
  lineHeight: 1.6,
  baselineUnit: 4, // px
  // Sidebar layout
  railWidth: 36, // px
  minimapWidth: 48, // px (3rem at 16px base)
  gutterLeft: 32, // px (2rem)
  gutterRight: 40, // px (2.5rem)
  overlayDuration: 0.3, // seconds
  hoverDelay: 400, // ms
  leaveGrace: 100, // ms
} as const;

// ── State shape ───────────────────────────────────────────────────────────

export interface PlaygroundState {
  open: boolean;
  hudVisible: boolean;
  drawerHeight: number;

  // Viewport simulation (actual browser resize)
  targetWidth: number | null;
  savedWindowSize: { w: number; h: number } | null;

  // Layout token overrides (null = use CSS default)
  quoteMaxWidth: number | null;
  gridGap: number | null;
  maxWidth: number | null;
  spacingScale: number | null;
  radiusScale: number | null;

  // Type scale
  baseFontSize: number | null;
  typeScaleRatio: number | null;
  lineHeight: number | null;

  // Active breakpoint set key
  breakpointSet: string;

  // Visual aids
  gridOverlay: boolean;
  baselineGrid: boolean;
  baselineUnit: number;

  // Dark mode override (null = follow OS)
  darkMode: "light" | "dark" | null;

  // Type scale preset name (for display)
  typeScalePreset: string | null;

  // Sidebar layout overrides (null = use CSS/JS defaults)
  railWidth: number | null;
  minimapWidth: number | null;
  gutterLeft: number | null;
  gutterRight: number | null;
  overlayDuration: number | null;
  hoverDelay: number | null;     // JS-only (hover intent delay, ms)
  leaveGrace: number | null;     // JS-only (leave grace period, ms)

  // Overlay content animation variant (null = "curtain" default)
  overlayStyle: "curtain" | "ios" | null;
}

// ── sessionStorage helpers ────────────────────────────────────────────────

function saveState(s: PlaygroundState): void {
  try {
    sessionStorage.setItem(SS_KEY, JSON.stringify(s));
  } catch {
    // sessionStorage full or unavailable
  }
}

function loadState(): PlaygroundState {
  const defaults: PlaygroundState = {
    open: false,
    hudVisible: false,
    drawerHeight: 220,
    targetWidth: null,
    savedWindowSize: null,
    quoteMaxWidth: null,
    gridGap: null,
    maxWidth: null,
    spacingScale: null,
    radiusScale: null,
    baseFontSize: null,
    typeScaleRatio: null,
    lineHeight: null,
    breakpointSet: "bristlenose",
    gridOverlay: false,
    baselineGrid: false,
    baselineUnit: 4,
    darkMode: null,
    typeScalePreset: null,
    railWidth: null,
    minimapWidth: null,
    gutterLeft: null,
    gutterRight: null,
    overlayDuration: null,
    hoverDelay: null,
    leaveGrace: null,
    overlayStyle: null,
  };
  try {
    const raw = sessionStorage.getItem(SS_KEY);
    if (!raw) return defaults;
    const parsed = JSON.parse(raw);
    return { ...defaults, ...parsed };
  } catch {
    return defaults;
  }
}

// ── Module-level store ────────────────────────────────────────────────────

let state: PlaygroundState = loadState();
const listeners = new Set<() => void>();

function getSnapshot(): PlaygroundState {
  return state;
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

function setState(updater: (prev: PlaygroundState) => PlaygroundState): void {
  state = updater(state);
  saveState(state);
  applyOverrides(state);
  listeners.forEach((l) => l());
}

// ── CSS injection ─────────────────────────────────────────────────────────

const STYLE_ID = "bn-playground-overrides";

function getOrCreateStyle(): HTMLStyleElement {
  let el = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (!el) {
    el = document.createElement("style");
    el.id = STYLE_ID;
    document.head.appendChild(el);
  }
  return el;
}

function applyOverrides(s: PlaygroundState): void {
  const el = getOrCreateStyle();
  const rootVars: string[] = [];
  const rules: string[] = [];

  // Layout tokens
  if (s.quoteMaxWidth !== null)
    rootVars.push(`--bn-quote-max-width: ${s.quoteMaxWidth}rem`);
  if (s.gridGap !== null) rootVars.push(`--bn-grid-gap: ${s.gridGap}rem`);
  if (s.maxWidth !== null) rootVars.push(`--bn-max-width: ${s.maxWidth}rem`);

  // Spacing scale (multiply defaults)
  if (s.spacingScale !== null && s.spacingScale !== 1.0) {
    rootVars.push(`--bn-space-xs: calc(0.15rem * ${s.spacingScale})`);
    rootVars.push(`--bn-space-sm: calc(0.35rem * ${s.spacingScale})`);
    rootVars.push(`--bn-space-md: calc(0.75rem * ${s.spacingScale})`);
    rootVars.push(`--bn-space-lg: calc(1.5rem * ${s.spacingScale})`);
    rootVars.push(`--bn-space-xl: calc(2rem * ${s.spacingScale})`);
  }

  // Radius scale
  if (s.radiusScale !== null && s.radiusScale !== 1.0) {
    rootVars.push(`--bn-radius-sm: calc(3px * ${s.radiusScale})`);
    rootVars.push(`--bn-radius-md: calc(6px * ${s.radiusScale})`);
    rootVars.push(`--bn-radius-lg: calc(8px * ${s.radiusScale})`);
  }

  // Type scale: base font size (global — everything is rem-based)
  if (s.baseFontSize !== null) {
    rules.push(`html { font-size: ${s.baseFontSize}px !important; }`);
  }

  // Line height
  if (s.lineHeight !== null) {
    rules.push(`body { line-height: ${s.lineHeight} !important; }`);
  }

  // Type scale ratio: override heading sizes
  if (s.typeScaleRatio !== null) {
    const base = s.baseFontSize ?? TOKEN_DEFAULTS.baseFontSize;
    const r = s.typeScaleRatio;
    const h3 = base * r;
    const h2 = base * r * r;
    const h1 = base * r * r * r;
    // Convert to rem (relative to potentially overridden base)
    const remBase = s.baseFontSize ?? 16;
    rules.push(`h3 { font-size: ${(h3 / remBase).toFixed(3)}rem !important; }`);
    rules.push(`h2 { font-size: ${(h2 / remBase).toFixed(3)}rem !important; }`);
    rules.push(`h1 { font-size: ${(h1 / remBase).toFixed(3)}rem !important; }`);
  }

  // Sidebar layout tokens
  if (s.railWidth !== null)
    rootVars.push(`--bn-rail-width: ${s.railWidth}px`);
  if (s.minimapWidth !== null)
    rootVars.push(`--bn-minimap-width: ${s.minimapWidth}px`);
  if (s.gutterLeft !== null)
    rootVars.push(`--bn-gutter-left: ${s.gutterLeft}px`);
  if (s.gutterRight !== null)
    rootVars.push(`--bn-gutter-right: ${s.gutterRight}px`);
  if (s.overlayDuration !== null)
    rootVars.push(`--bn-overlay-duration: ${s.overlayDuration}s`);

  // Baseline grid
  rootVars.push(`--bn-baseline: ${s.baselineUnit}px`);

  // Combine
  let css = "";
  if (rootVars.length > 0) {
    css += `:root { ${rootVars.join("; ")}; }\n`;
  }
  css += rules.join("\n");
  el.textContent = css;

  // Body classes for visual aids
  document.body.classList.toggle("bn-show-baseline", s.baselineGrid);
  document.body.classList.toggle("bn-show-grid-overlay", s.gridOverlay);

  // Dark mode override
  if (s.darkMode) {
    document.documentElement.setAttribute("data-theme", s.darkMode);
  } else {
    document.documentElement.removeAttribute("data-theme");
  }
}

// ── Actions ───────────────────────────────────────────────────────────────

export function togglePlayground(): void {
  setState((prev) => ({ ...prev, open: !prev.open }));
}

export function toggleHUD(): void {
  setState((prev) => ({ ...prev, hudVisible: !prev.hudVisible }));
}

export function setDrawerHeight(height: number): void {
  setState((prev) => ({
    ...prev,
    drawerHeight: Math.max(100, Math.min(600, height)),
  }));
}

export function setTargetWidth(width: number | null): void {
  setState((prev) => {
    // Save current window size before first resize
    const saved =
      prev.savedWindowSize ?? (width !== null ? { w: window.outerWidth, h: window.outerHeight } : null);

    if (width !== null) {
      // Compute window chrome offset
      const chromeWidth = window.outerWidth - window.innerWidth;
      try {
        window.resizeTo(width + chromeWidth, window.outerHeight);
      } catch {
        // resizeTo may be blocked
      }
    } else if (prev.savedWindowSize) {
      // Restore original size
      try {
        window.resizeTo(prev.savedWindowSize.w, prev.savedWindowSize.h);
      } catch {
        // may be blocked
      }
    }

    return {
      ...prev,
      targetWidth: width,
      savedWindowSize: width !== null ? saved : null,
    };
  });
}

export function setQuoteMaxWidth(v: number | null): void {
  setState((prev) => ({ ...prev, quoteMaxWidth: v }));
}

export function setGridGap(v: number | null): void {
  setState((prev) => ({ ...prev, gridGap: v }));
}

export function setMaxWidth(v: number | null): void {
  setState((prev) => ({ ...prev, maxWidth: v }));
}

export function setSpacingScale(v: number | null): void {
  setState((prev) => ({ ...prev, spacingScale: v }));
}

export function setRadiusScale(v: number | null): void {
  setState((prev) => ({ ...prev, radiusScale: v }));
}

export function setBaseFontSize(v: number | null): void {
  setState((prev) => ({ ...prev, baseFontSize: v }));
}

export function setTypeScaleRatio(v: number | null): void {
  setState((prev) => ({ ...prev, typeScaleRatio: v }));
}

export function setLineHeight(v: number | null): void {
  setState((prev) => ({ ...prev, lineHeight: v }));
}

export function setBreakpointSet(key: string): void {
  setState((prev) => ({ ...prev, breakpointSet: key }));
}

export function toggleGridOverlay(): void {
  setState((prev) => ({ ...prev, gridOverlay: !prev.gridOverlay }));
}

export function toggleBaselineGrid(): void {
  setState((prev) => ({ ...prev, baselineGrid: !prev.baselineGrid }));
}

export function setBaselineUnit(v: number): void {
  setState((prev) => ({ ...prev, baselineUnit: v }));
}

export function setDarkMode(v: "light" | "dark" | null): void {
  setState((prev) => ({ ...prev, darkMode: v }));
}

export function setTypeScalePreset(name: string | null): void {
  setState((prev) => ({ ...prev, typeScalePreset: name }));
}

// Sidebar layout setters
export function setRailWidth(v: number | null): void {
  setState((prev) => ({ ...prev, railWidth: v }));
}
export function setMinimapWidth(v: number | null): void {
  setState((prev) => ({ ...prev, minimapWidth: v }));
}
export function setGutterLeft(v: number | null): void {
  setState((prev) => ({ ...prev, gutterLeft: v }));
}
export function setGutterRight(v: number | null): void {
  setState((prev) => ({ ...prev, gutterRight: v }));
}
export function setOverlayDuration(v: number | null): void {
  setState((prev) => ({ ...prev, overlayDuration: v }));
}
export function setHoverDelay(v: number | null): void {
  setState((prev) => ({ ...prev, hoverDelay: v }));
}
export function setLeaveGrace(v: number | null): void {
  setState((prev) => ({ ...prev, leaveGrace: v }));
}
export function setOverlayStyle(v: "curtain" | "ios" | null): void {
  setState((prev) => ({ ...prev, overlayStyle: v }));
}

/** Reset all overrides to CSS defaults. */
export function resetPlayground(): void {
  // Restore window size if we resized
  if (state.savedWindowSize) {
    try {
      window.resizeTo(state.savedWindowSize.w, state.savedWindowSize.h);
    } catch {
      // may be blocked
    }
  }

  setState(() => ({
    open: state.open, // keep panel open
    hudVisible: state.hudVisible, // keep HUD visible
    drawerHeight: state.drawerHeight, // keep drawer height
    targetWidth: null,
    savedWindowSize: null,
    quoteMaxWidth: null,
    gridGap: null,
    maxWidth: null,
    spacingScale: null,
    radiusScale: null,
    baseFontSize: null,
    typeScaleRatio: null,
    lineHeight: null,
    breakpointSet: "bristlenose",
    gridOverlay: false,
    baselineGrid: false,
    baselineUnit: 4,
    darkMode: null,
    typeScalePreset: null,
    railWidth: null,
    minimapWidth: null,
    gutterLeft: null,
    gutterRight: null,
    overlayDuration: null,
    hoverDelay: null,
    leaveGrace: null,
    overlayStyle: null,
  }));
}

/** Full reset (including panel state). Used for test isolation. */
export function resetPlaygroundStore(): void {
  const el = document.getElementById(STYLE_ID);
  if (el) el.remove();
  document.body.classList.remove("bn-show-baseline", "bn-show-grid-overlay");
  document.documentElement.removeAttribute("data-theme");

  state = {
    open: false,
    hudVisible: false,
    drawerHeight: 220,
    targetWidth: null,
    savedWindowSize: null,
    quoteMaxWidth: null,
    gridGap: null,
    maxWidth: null,
    spacingScale: null,
    radiusScale: null,
    baseFontSize: null,
    typeScaleRatio: null,
    lineHeight: null,
    breakpointSet: "bristlenose",
    gridOverlay: false,
    baselineGrid: false,
    baselineUnit: 4,
    darkMode: null,
    typeScalePreset: null,
    railWidth: null,
    minimapWidth: null,
    gutterLeft: null,
    gutterRight: null,
    overlayDuration: null,
    hoverDelay: null,
    leaveGrace: null,
    overlayStyle: null,
  };
  try {
    sessionStorage.removeItem(SS_KEY);
  } catch {
    // ignore
  }
  listeners.forEach((l) => l());
}

// ── React hook ────────────────────────────────────────────────────────────

/** Subscribe to the playground store. Re-renders on any mutation. */
export function usePlaygroundStore(): PlaygroundState {
  return useSyncExternalStore(subscribe, getSnapshot);
}
