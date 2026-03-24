/**
 * InspectorPanel — collapsible bottom panel for heatmap matrices.
 *
 * DevTools-style inspector sitting below the signal cards in the Analysis tab.
 * Collapsed by default: 28px bar with grid icon + "Heatmap" label. Opens to
 * show source tabs and a scrollable heatmap body.
 *
 * @module InspectorPanel
 */

import {
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  useInspectorStore,
  toggleInspector,
  setInspectorSource,
  setInspectorDimension,
  setInspectorHeight,
  MIN_HEIGHT,
  DEFAULT_HEIGHT,
} from "../contexts/InspectorStore";
import { useVerticalDragResize } from "../hooks/useVerticalDragResize";
import { useTranslation } from "react-i18next";

// ── DimensionToggle — for the heatmap table's top-left <th> cell ─────────

export function DimensionToggle({ hasBoth }: { hasBoth: boolean }) {
  const { activeDimension } = useInspectorStore();
  const { t } = useTranslation();

  if (!hasBoth) {
    return <>{activeDimension === "section" ? t("analysis.section") : t("analysis.theme")}</>;
  }

  return (
    <span className="dimension-toggle" role="radiogroup" aria-label={t("analysis.dimension")}>
      <button
        className={`dimension-btn${activeDimension === "section" ? " active" : ""}`}
        role="radio"
        aria-checked={activeDimension === "section"}
        onClick={() => setInspectorDimension("section")}
      >
        {t("analysis.section")}
      </button>
      <button
        className={`dimension-btn${activeDimension === "theme" ? " active" : ""}`}
        role="radio"
        aria-checked={activeDimension === "theme"}
        onClick={() => setInspectorDimension("theme")}
      >
        {t("analysis.theme")}
      </button>
    </span>
  );
}

// ── Types ────────────────────────────────────────────────────────────────

export interface InspectorSource {
  /** Unique key for this source (e.g. "sentiment", "cb-1"). */
  key: string;
  /** Tab label (e.g. "Sentiment", "UX Research"). */
  label: string;
  /** ReactNode to render when dimension is "section". */
  sectionContent?: ReactNode;
  /** ReactNode to render when dimension is "theme". */
  themeContent?: ReactNode;
}

// ── Constants ────────────────────────────────────────────────────────────

const SHIMMER_KEY = "bn-inspector-shimmer-count";
const SHIMMER_MAX = 3;

// ── Grid icon SVGs ───────────────────────────────────────────────────────

function GridIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <rect x="1" y="1" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="8" y="1" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="1" y="8" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3" />
      <rect x="8" y="8" width="5" height="5" rx="1" stroke="currentColor" strokeWidth="1.3" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
      <path d="M3 3L11 11M11 3L3 11" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

// ── Component ────────────────────────────────────────────────────────────

interface InspectorPanelProps {
  /** Available heatmap sources — each provides up to 2 dimensions. */
  sources: InspectorSource[];
  /** Callback when a signal card focus should trigger shimmer. */
  shimmerTrigger?: number;
}

export function InspectorPanel({ sources, shimmerTrigger }: InspectorPanelProps) {
  const { open, height, hasManualHeight, activeSource, activeDimension } =
    useInspectorStore();
  const { t } = useTranslation();

  const panelRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const titleRef = useRef<HTMLSpanElement>(null);

  // ── Close animation state ───────────────────────────────────────────
  // When the store transitions open→closed, hold a "closing" state for
  // 75ms so the CSS exit animation plays before content is removed.
  const [closing, setClosing] = useState(false);
  const prevOpenRef = useRef(open);

  useEffect(() => {
    if (prevOpenRef.current && !open) {
      setClosing(true);
      const timer = setTimeout(() => setClosing(false), 75);
      return () => clearTimeout(timer);
    }
    prevOpenRef.current = open;
  }, [open]);

  // Resolve the active source — fall back to the first available
  const resolvedSource =
    sources.find((s) => s.key === activeSource) ?? sources[0] ?? null;

  // Determine which content to show
  const activeContent = resolvedSource
    ? activeDimension === "theme"
      ? resolvedSource.themeContent ?? resolvedSource.sectionContent
      : resolvedSource.sectionContent ?? resolvedSource.themeContent
    : null;

  // ── Auto-height on first open ───────────────────────────────────────

  const measuredRef = useRef(false);

  useLayoutEffect(() => {
    if (!open || hasManualHeight || measuredRef.current) return;
    if (!bodyRef.current) return;

    // Measure after render
    const rAF = requestAnimationFrame(() => {
      if (!bodyRef.current) return;
      const contentH = bodyRef.current.scrollHeight;
      // Add handle (28px) + tabs (32px) heights
      const totalH = contentH + 28 + 32;
      const maxVh = window.innerHeight * 0.7;
      const autoH = Math.max(MIN_HEIGHT, Math.min(totalH, maxVh));
      setInspectorHeight(autoH);
      // Mark as measured but keep hasManualHeight from the store action
      measuredRef.current = true;
    });

    return () => cancelAnimationFrame(rAF);
  }, [open, hasManualHeight]);

  // Reset measured flag when panel closes
  useEffect(() => {
    if (!open) measuredRef.current = false;
  }, [open]);

  // ── Shimmer ─────────────────────────────────────────────────────────

  useEffect(() => {
    if (shimmerTrigger === undefined || shimmerTrigger === 0) return;
    if (open) return; // Only shimmer when collapsed
    if (!titleRef.current) return;

    let count = 0;
    try {
      count = parseInt(sessionStorage.getItem(SHIMMER_KEY) ?? "0", 10);
    } catch {
      // sessionStorage unavailable
    }
    if (count >= SHIMMER_MAX) return;

    try {
      sessionStorage.setItem(SHIMMER_KEY, String(count + 1));
    } catch {
      // ignore
    }

    const el = titleRef.current;
    el.classList.remove("shimmer");
    // Force reflow to restart animation
    void el.offsetWidth;
    el.classList.add("shimmer");
    const handler = () => el.classList.remove("shimmer");
    el.addEventListener("animationend", handler, { once: true });
  }, [shimmerTrigger, open]);

  // ── Drag resize ─────────────────────────────────────────────────────

  const { handlePointerDown, handleKeyDown, isDragging } = useVerticalDragResize({
    containerRef: panelRef,
    currentHeight: height,
    isOpen: open,
  });
  void isDragging;

  // ── Handlers ────────────────────────────────────────────────────────

  const handleIconClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      toggleInspector();
    },
    [],
  );

  const handleTabClick = useCallback(
    (key: string) => {
      setInspectorSource(key);
    },
    [],
  );

  // ── Render ──────────────────────────────────────────────────────────

  if (sources.length === 0) return null;

  // During closing, keep content visible so exit animation plays
  const panelClass = open
    ? "inspector-panel"
    : closing
      ? "inspector-panel closing"
      : "inspector-panel collapsed";
  // Keep the height during closing so the panel doesn't jump
  const panelStyle = (open || closing)
    ? { "--inspector-height": `${height}px` } as React.CSSProperties
    : undefined;

  return (
    <div
      ref={panelRef}
      className={panelClass}
      style={panelStyle}
      data-testid="bn-inspector-panel"
    >
      {/* Handle bar */}
      <div className="inspector-handle">
        <button
          className="inspector-icon-btn"
          onClick={handleIconClick}
          title={open ? t("analysis.heatmapOpen") : t("analysis.heatmapClosed")}
          aria-label={open ? t("analysis.heatmapCloseLabel") : t("analysis.heatmapOpenLabel")}
          data-testid="inspector-toggle"
        >
          {open ? <CloseIcon /> : <GridIcon />}
        </button>

        <span
          ref={titleRef}
          className="inspector-handle-title"
          data-testid="inspector-title"
        >
          {t("analysis.heatmap")}
        </span>

        <span
          className="inspector-handle-grip"
          role="separator"
          aria-orientation="horizontal"
          aria-valuenow={height}
          aria-valuemin={MIN_HEIGHT}
          aria-valuemax={DEFAULT_HEIGHT}
          tabIndex={0}
          onPointerDown={handlePointerDown}
          onKeyDown={handleKeyDown}
          data-testid="inspector-grip"
        />
      </div>

      {/* Source tabs */}
      <div className="inspector-tabs" role="tablist" aria-label={t("analysis.heatmapSources")}>
        {sources.map((s) => (
          <button
            key={s.key}
            className={`inspector-tab${resolvedSource?.key === s.key ? " active" : ""}`}
            role="tab"
            aria-selected={resolvedSource?.key === s.key}
            onClick={() => handleTabClick(s.key)}
            data-testid={`inspector-tab-${s.key}`}
          >
            {s.label}
          </button>
        ))}
      </div>

      {/* Body */}
      <div
        ref={bodyRef}
        className="inspector-body"
        role="tabpanel"
        data-testid="inspector-body"
      >
        {activeContent}
      </div>
    </div>
  );
}
