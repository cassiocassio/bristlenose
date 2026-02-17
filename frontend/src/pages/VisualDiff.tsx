/**
 * VisualDiff — dev-only page for comparing Jinja2 and React sessions tables.
 *
 * Three view modes:
 *   1. Side by side — Jinja2 left, React right
 *   2. Overlay — both stacked, opacity slider blends between them
 *   3. Toggle — Space key swaps instantly between the two
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { SessionsTable } from "../islands/SessionsTable";
import "./visual-diff.css";

type ViewMode = "side-by-side" | "overlay" | "toggle";

export function VisualDiff() {
  const [jinjaHtml, setJinjaHtml] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<ViewMode>("side-by-side");
  const [opacity, setOpacity] = useState(50);
  const [showJinja, setShowJinja] = useState(true); // for toggle mode
  const [cssLoaded, setCssLoaded] = useState(false);

  // Fetch Jinja2 HTML fragment
  useEffect(() => {
    fetch("/api/dev/sessions-table-html?project_id=1")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.text();
      })
      .then(setJinjaHtml)
      .catch((err: Error) => setError(err.message));
  }, []);

  // Load report CSS so both tables share the same styles
  useEffect(() => {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = "/report/assets/bristlenose-theme.css";
    link.onload = () => setCssLoaded(true);
    link.onerror = () => {
      // Fallback: CSS might be inline in the report, not a separate file.
      // Still mark as loaded so the page renders — styles may be partial.
      setCssLoaded(true);
    };
    document.head.appendChild(link);
    return () => {
      document.head.removeChild(link);
    };
  }, []);

  // Keyboard: Space/T toggles in toggle mode, 1/2/3 switches modes
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement) return;
      if (e.key === " " || e.key === "t" || e.key === "T") {
        e.preventDefault();
        if (mode === "toggle") {
          setShowJinja((prev) => !prev);
        } else {
          setMode("toggle");
        }
      } else if (e.key === "1") {
        setMode("side-by-side");
      } else if (e.key === "2") {
        setMode("overlay");
      } else if (e.key === "3") {
        setMode("toggle");
      }
    },
    [mode],
  );

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleKeyDown]);

  // Synced scroll for side-by-side mode
  const leftRef = useRef<HTMLDivElement>(null);
  const rightRef = useRef<HTMLDivElement>(null);
  const scrollingRef = useRef(false);

  const syncScroll = useCallback(
    (source: "left" | "right") => {
      if (scrollingRef.current) return;
      scrollingRef.current = true;
      const src = source === "left" ? leftRef.current : rightRef.current;
      const dst = source === "left" ? rightRef.current : leftRef.current;
      if (src && dst) {
        dst.scrollTop = src.scrollTop;
      }
      requestAnimationFrame(() => {
        scrollingRef.current = false;
      });
    },
    [],
  );

  if (error) {
    return (
      <div className="vd-page">
        <div className="vd-error">Failed to load Jinja2 HTML: {error}</div>
      </div>
    );
  }

  if (!jinjaHtml || !cssLoaded) {
    return (
      <div className="vd-page">
        <div className="vd-loading">Loading both table versions…</div>
      </div>
    );
  }

  return (
    <div className="vd-page">
      <Toolbar
        mode={mode}
        onModeChange={setMode}
        opacity={opacity}
        onOpacityChange={setOpacity}
        showJinja={showJinja}
      />

      {mode === "side-by-side" && (
        <div className="vd-side-by-side">
          <div
            className="vd-pane"
            ref={leftRef}
            onScroll={() => syncScroll("left")}
          >
            <div className="vd-pane-label jinja">Jinja2 (static report)</div>
            <div dangerouslySetInnerHTML={{ __html: jinjaHtml }} />
          </div>
          <div
            className="vd-pane"
            ref={rightRef}
            onScroll={() => syncScroll("right")}
          >
            <div className="vd-pane-label react">React (serve mode)</div>
            <SessionsTable projectId="1" />
          </div>
        </div>
      )}

      {mode === "overlay" && (
        <div className="vd-overlay-container">
          <div
            className="vd-overlay-layer jinja"
            style={{ opacity: (100 - opacity) / 100 }}
          >
            <div className="vd-pane-label jinja">
              Jinja2 — {100 - opacity}% opacity
            </div>
            <div dangerouslySetInnerHTML={{ __html: jinjaHtml }} />
          </div>
          <div
            className="vd-overlay-layer react"
            style={{ opacity: opacity / 100 }}
          >
            <div className="vd-pane-label react">
              React — {opacity}% opacity
            </div>
            <SessionsTable projectId="1" />
          </div>
        </div>
      )}

      {mode === "toggle" && (
        <div className="vd-toggle-container">
          {showJinja ? (
            <>
              <div className="vd-pane-label jinja">
                Jinja2 (static report) — press Space to toggle
              </div>
              <div dangerouslySetInnerHTML={{ __html: jinjaHtml }} />
            </>
          ) : (
            <>
              <div className="vd-pane-label react">
                React (serve mode) — press Space to toggle
              </div>
              <SessionsTable projectId="1" />
            </>
          )}
        </div>
      )}
    </div>
  );
}

function Toolbar({
  mode,
  onModeChange,
  opacity,
  onOpacityChange,
  showJinja,
}: {
  mode: ViewMode;
  onModeChange: (m: ViewMode) => void;
  opacity: number;
  onOpacityChange: (v: number) => void;
  showJinja: boolean;
}) {
  return (
    <div className="vd-toolbar">
      <h1>Visual Diff</h1>

      <div className="vd-toolbar-group">
        <button
          className={mode === "side-by-side" ? "active" : ""}
          onClick={() => onModeChange("side-by-side")}
        >
          Side by Side
        </button>
        <button
          className={mode === "overlay" ? "active" : ""}
          onClick={() => onModeChange("overlay")}
        >
          Overlay
        </button>
        <button
          className={mode === "toggle" ? "active" : ""}
          onClick={() => onModeChange("toggle")}
        >
          Toggle
        </button>
      </div>

      {mode === "overlay" && (
        <div className="vd-toolbar-group">
          <label>Jinja2</label>
          <input
            type="range"
            min={0}
            max={100}
            value={opacity}
            onChange={(e) => onOpacityChange(Number(e.target.value))}
          />
          <label>React</label>
        </div>
      )}

      <span className="vd-hint">
        <kbd>1</kbd> side-by-side{" "}
        <kbd>2</kbd> overlay{" "}
        <kbd>3</kbd> toggle{" "}
        <kbd>Space</kbd> swap
        {mode === "toggle" && (
          <> — showing {showJinja ? "Jinja2" : "React"}</>
        )}
      </span>
    </div>
  );
}
