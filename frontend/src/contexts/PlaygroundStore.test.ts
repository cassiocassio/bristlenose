import { describe, it, expect, beforeEach } from "vitest";
import {
  resetPlaygroundStore,
  togglePlayground,
  toggleHUD,
  setQuoteMaxWidth,
  setGridGap,
  setMaxWidth,
  setSpacingScale,
  setRadiusScale,
  setBaseFontSize,
  setTypeScaleRatio,
  setLineHeight,
  toggleGridOverlay,
  toggleBaselineGrid,
  setBaselineUnit,
  setDarkMode,
  resetPlayground,
  setRailWidth,
  setMinimapWidth,
  setGutterLeft,
  setGutterRight,
  setOverlayDuration,
  setHoverDelay,
  setLeaveGrace,
} from "./PlaygroundStore";

// Module-level store persists across tests — always reset.
beforeEach(() => {
  resetPlaygroundStore();
});

describe("PlaygroundStore", () => {
  it("starts with all overrides null", () => {
    // After reset, no style element should exist
    const el = document.getElementById("bn-playground-overrides");
    expect(el).toBeNull();
  });

  it("togglePlayground toggles open state", () => {
    // Toggle creates the style element as a side effect
    togglePlayground();
    // The style element is created on first state change
    const el = document.getElementById("bn-playground-overrides");
    expect(el).toBeTruthy();
  });

  it("setQuoteMaxWidth injects CSS override", () => {
    setQuoteMaxWidth(30);
    const el = document.getElementById("bn-playground-overrides");
    expect(el).toBeTruthy();
    expect(el!.textContent).toContain("--bn-quote-max-width: 30rem");
  });

  it("setGridGap injects CSS override", () => {
    setGridGap(2);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-grid-gap: 2rem");
  });

  it("setMaxWidth injects CSS override", () => {
    setMaxWidth(60);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-max-width: 60rem");
  });

  it("setSpacingScale injects calc-based overrides", () => {
    setSpacingScale(1.5);
    const el = document.getElementById("bn-playground-overrides");
    const css = el!.textContent!;
    expect(css).toContain("--bn-space-xs: calc(0.15rem * 1.5)");
    expect(css).toContain("--bn-space-lg: calc(1.5rem * 1.5)");
  });

  it("setSpacingScale at 1.0 does not inject spacing overrides", () => {
    setSpacingScale(1.0);
    const el = document.getElementById("bn-playground-overrides");
    // spacingScale === 1.0 should not emit spacing vars
    expect(el!.textContent).not.toContain("--bn-space-xs");
  });

  it("setRadiusScale injects calc-based overrides", () => {
    setRadiusScale(2);
    const el = document.getElementById("bn-playground-overrides");
    const css = el!.textContent!;
    expect(css).toContain("--bn-radius-sm: calc(3px * 2)");
    expect(css).toContain("--bn-radius-md: calc(6px * 2)");
  });

  it("setBaseFontSize injects html font-size", () => {
    setBaseFontSize(18);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("html { font-size: 18px !important; }");
  });

  it("setTypeScaleRatio injects heading sizes", () => {
    setTypeScaleRatio(1.2);
    const el = document.getElementById("bn-playground-overrides");
    const css = el!.textContent!;
    expect(css).toContain("h3 { font-size:");
    expect(css).toContain("h2 { font-size:");
    expect(css).toContain("h1 { font-size:");
  });

  it("setLineHeight injects body line-height", () => {
    setLineHeight(1.8);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("body { line-height: 1.8 !important; }");
  });

  it("toggleBaselineGrid adds body class", () => {
    toggleBaselineGrid();
    expect(document.body.classList.contains("bn-show-baseline")).toBe(true);
    toggleBaselineGrid();
    expect(document.body.classList.contains("bn-show-baseline")).toBe(false);
  });

  it("toggleGridOverlay adds body class", () => {
    toggleGridOverlay();
    expect(document.body.classList.contains("bn-show-grid-overlay")).toBe(true);
    toggleGridOverlay();
    expect(document.body.classList.contains("bn-show-grid-overlay")).toBe(false);
  });

  it("setDarkMode sets data-theme attribute", () => {
    setDarkMode("dark");
    expect(document.documentElement.getAttribute("data-theme")).toBe("dark");
    setDarkMode("light");
    expect(document.documentElement.getAttribute("data-theme")).toBe("light");
    setDarkMode(null);
    expect(document.documentElement.getAttribute("data-theme")).toBeNull();
  });

  it("setBaselineUnit updates CSS variable", () => {
    setBaselineUnit(8);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-baseline: 8px");
  });

  it("resetPlayground clears all overrides but keeps panel state", () => {
    togglePlayground(); // open
    toggleHUD(); // show HUD
    setQuoteMaxWidth(30);
    setBaseFontSize(18);
    toggleBaselineGrid();

    resetPlayground();

    const el = document.getElementById("bn-playground-overrides");
    // Should not contain quote-max-width override
    expect(el!.textContent).not.toContain("--bn-quote-max-width: 30rem");
    // Baseline grid class should be removed
    expect(document.body.classList.contains("bn-show-baseline")).toBe(false);
  });

  it("resetPlaygroundStore removes style element entirely", () => {
    setQuoteMaxWidth(30);
    expect(document.getElementById("bn-playground-overrides")).toBeTruthy();

    resetPlaygroundStore();

    expect(document.getElementById("bn-playground-overrides")).toBeNull();
    expect(document.body.classList.contains("bn-show-baseline")).toBe(false);
    expect(document.body.classList.contains("bn-show-grid-overlay")).toBe(false);
  });

  it("persists to sessionStorage", () => {
    setQuoteMaxWidth(25);
    const raw = sessionStorage.getItem("bn-playground");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.quoteMaxWidth).toBe(25);
  });

  it("null overrides emit no CSS for that token", () => {
    // Set and then clear
    setQuoteMaxWidth(30);
    setQuoteMaxWidth(null);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).not.toContain("--bn-quote-max-width");
  });
});

describe("PlaygroundStore — sidebar layout tokens", () => {
  it("setRailWidth injects CSS override", () => {
    setRailWidth(48);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-rail-width: 48px");
  });

  it("setMinimapWidth injects CSS override", () => {
    setMinimapWidth(64);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-minimap-width: 64px");
  });

  it("setGutterLeft injects CSS override", () => {
    setGutterLeft(48);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-gutter-left: 48px");
  });

  it("setGutterRight injects CSS override", () => {
    setGutterRight(56);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-gutter-right: 56px");
  });

  it("setOverlayDuration injects CSS override", () => {
    setOverlayDuration(0.5);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).toContain("--bn-overlay-duration: 0.5s");
  });

  it("setHoverDelay is JS-only (no CSS emitted)", () => {
    setHoverDelay(600);
    const el = document.getElementById("bn-playground-overrides");
    // hoverDelay is a JS-only value, not a CSS token
    expect(el!.textContent).not.toContain("hover");
  });

  it("setLeaveGrace is JS-only (no CSS emitted)", () => {
    setLeaveGrace(200);
    const el = document.getElementById("bn-playground-overrides");
    // leaveGrace is a JS-only value, not a CSS token
    expect(el!.textContent).not.toContain("grace");
  });

  it("sidebar layout values persist to sessionStorage", () => {
    setRailWidth(50);
    setHoverDelay(500);
    const raw = sessionStorage.getItem("bn-playground");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(raw!);
    expect(parsed.railWidth).toBe(50);
    expect(parsed.hoverDelay).toBe(500);
  });

  it("null sidebar layout values emit no CSS", () => {
    setRailWidth(48);
    setRailWidth(null);
    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).not.toContain("--bn-rail-width");
  });

  it("resetPlayground clears sidebar layout overrides", () => {
    setRailWidth(48);
    setGutterLeft(64);
    setHoverDelay(800);

    resetPlayground();

    const el = document.getElementById("bn-playground-overrides");
    expect(el!.textContent).not.toContain("--bn-rail-width");
    expect(el!.textContent).not.toContain("--bn-gutter-left");
  });
});
