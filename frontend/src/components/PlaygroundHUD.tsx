/**
 * PlaygroundHUD — thin metrics bar across the top of the viewport.
 *
 * Displays: viewport width, CSS column count, actual card width,
 * ~words/line estimate, nearest device name, active breakpoint zone.
 * Updates on window resize via requestAnimationFrame.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { usePlaygroundStore } from "../contexts/PlaygroundStore";
import {
  BREAKPOINT_SETS,
  getDeviceName,
  getBreakpointZone,
} from "../data/devicePresets";

interface HUDMetrics {
  viewportWidth: number;
  cols: number;
  cardWidth: number;
  wordsPerLine: number;
  device: string;
  zone: number;
  zoneCount: number;
}

const ZONE_COLOURS = [
  "#ef4444", // red: below first breakpoint
  "#f59e0b", // amber
  "#22c55e", // green
  "#3b82f6", // blue
  "#8b5cf6", // purple
  "#ec4899", // pink (if > 5 zones)
];

function measureMetrics(breakpoints: number[]): HUDMetrics {
  const w = window.innerWidth;
  const qg = document.querySelector(".quote-group") as HTMLElement | null;
  let cols = 1;
  let cardWidth = 0;
  let wordsPerLine = 0;

  if (qg) {
    const style = getComputedStyle(qg);
    if (style.display === "grid") {
      cols = style.gridTemplateColumns
        .split(/\s+/)
        .filter(Boolean).length;
    }
    const firstCard = qg.querySelector("blockquote");
    if (firstCard) {
      cardWidth = Math.round(firstCard.getBoundingClientRect().width);
      // Estimate: subtract padding (16+16), timecode (~50px), action btns (~72px)
      const textW = cardWidth - 16 - 16 - 50 - 72;
      const charsPerLine = textW / 7.5; // Inter at 16px ~7.5px/char
      wordsPerLine = Math.max(0, Math.round(charsPerLine / 6.2));
    }
  }

  return {
    viewportWidth: w,
    cols,
    cardWidth,
    wordsPerLine,
    device: getDeviceName(w),
    zone: getBreakpointZone(w, breakpoints),
    zoneCount: breakpoints.length + 1,
  };
}

export function PlaygroundHUD() {
  const pg = usePlaygroundStore();
  const [metrics, setMetrics] = useState<HUDMetrics>(() => {
    const bp = BREAKPOINT_SETS[pg.breakpointSet]?.values ?? [];
    return measureMetrics(bp);
  });
  const rafRef = useRef(0);

  const update = useCallback(() => {
    const bp = BREAKPOINT_SETS[pg.breakpointSet]?.values ?? [];
    setMetrics(measureMetrics(bp));
  }, [pg.breakpointSet]);

  useEffect(() => {
    const handleResize = () => {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = requestAnimationFrame(update);
    };
    window.addEventListener("resize", handleResize);
    // Also update on playground state changes (sidebar toggles, token changes)
    const timer = setInterval(update, 500);
    return () => {
      window.removeEventListener("resize", handleResize);
      cancelAnimationFrame(rafRef.current);
      clearInterval(timer);
    };
  }, [update]);

  if (!pg.hudVisible) return null;

  const bp = BREAKPOINT_SETS[pg.breakpointSet];

  return (
    <div className="pg-hud">
      <span>
        <span className="pg-hud-label">Viewport:</span>{" "}
        <span className="pg-hud-value">{metrics.viewportWidth}</span>
        <span className="pg-hud-label">px</span>
      </span>
      <span>
        <span className="pg-hud-label">Cols:</span>{" "}
        <span className="pg-hud-value">{metrics.cols}</span>
      </span>
      <span>
        <span className="pg-hud-label">Card:</span>{" "}
        <span className="pg-hud-value">{metrics.cardWidth}</span>
        <span className="pg-hud-label">px</span>
      </span>
      <span>
        <span className="pg-hud-label">~Words/line:</span>{" "}
        <span className="pg-hud-value">~{metrics.wordsPerLine}</span>
      </span>
      <span className="pg-hud-device">{metrics.device}</span>

      {bp && (
        <div className="pg-hud-bp-bar">
          {Array.from({ length: metrics.zoneCount }, (_, i) => (
            <div
              key={i}
              className="pg-hud-bp-segment"
              style={{
                flex: i <= metrics.zone ? 1 : 0,
                opacity: i <= metrics.zone ? 1 : 0.15,
                background: ZONE_COLOURS[i % ZONE_COLOURS.length],
              }}
            />
          ))}
        </div>
      )}

      <span className="pg-hud-bp-name">
        {bp?.name} [{bp?.values.join(", ")}]
      </span>
    </div>
  );
}
