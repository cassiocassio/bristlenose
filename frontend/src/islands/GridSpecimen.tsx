/**
 * GridSpecimen — the debug lens. Test content on a visible grid.
 *
 * Dev-only surface (route always registered at /report/specimen; the NavBar
 * link is dev-gated, the desktop entry lives in the Diagnostics menu's DEBUG
 * harness section). Renders:
 *
 *   1. A live measurement HUD — the numbers `__bnLayoutAudit` reports:
 *      toolbar inset received, body padding, content edges, viewport.
 *   2. Vivid fixed-position overlays marking the layout frame: content
 *      left/right edges, reading-width boundary, the first-ink datum line,
 *      and the gutter bands.
 *   3. Specimen content using the REAL theme classes (h1/h2/h3, body copy,
 *      quote cards, signal cards, radius tiers, keyline samples) so what's
 *      measured is the production CSS, not a mock of it.
 *
 * English-only by design (dev tool — same precedent as the responsive
 * playground; no locale keys). Debug overlay colours are deliberately
 * off-system: the point is to be loud, not to ship.
 *
 * See docs/design-lens-template.md — this page is the visual harness for
 * the lens-template invariants and the future Playwright alignment gate.
 */

import { useCallback, useEffect, useLayoutEffect, useState } from "react";

/** One measured snapshot of the layout frame. */
interface FrameMeasurements {
  toolbarInsetVar: string;
  bodyPadTop: number;
  bodyPadLeft: number;
  centerLeft: number;
  centerRight: number;
  centerPadLeft: number;
  centerPadRight: number;
  contentLeft: number;
  contentRight: number;
  viewportW: number;
  viewportH: number;
}

function measureFrame(): FrameMeasurements | null {
  const center = document.querySelector(".center");
  if (!center) return null;
  const centerRect = center.getBoundingClientRect();
  const centerStyle = getComputedStyle(center);
  const bodyStyle = getComputedStyle(document.body);
  const rootStyle = getComputedStyle(document.documentElement);
  const centerPadLeft = parseFloat(centerStyle.paddingLeft) || 0;
  const centerPadRight = parseFloat(centerStyle.paddingRight) || 0;
  return {
    toolbarInsetVar: rootStyle.getPropertyValue("--bn-toolbar-inset").trim() || "(unset)",
    bodyPadTop: parseFloat(bodyStyle.paddingTop) || 0,
    bodyPadLeft: parseFloat(bodyStyle.paddingLeft) || 0,
    centerLeft: centerRect.left,
    centerRight: centerRect.right,
    centerPadLeft,
    centerPadRight,
    contentLeft: centerRect.left + centerPadLeft,
    contentRight: centerRect.right - centerPadRight,
    viewportW: window.innerWidth,
    viewportH: window.innerHeight,
  };
}

/* Loud, deliberately off-system debug colours (dev-only surface). */
const EDGE_COLOUR = "#ff00aa"; // content edges — magenta
const GUTTER_COLOUR = "rgba(0, 200, 255, 0.18)"; // gutter bands — cyan wash
const DATUM_COLOUR = "#00e676"; // first-ink datum — green
const READING_COLOUR = "#ffab00"; // reading-width boundary — amber

const labelStyle: React.CSSProperties = {
  position: "absolute",
  top: 4,
  left: 4,
  font: "600 10px/1.2 ui-monospace, monospace",
  background: "rgba(0,0,0,0.72)",
  color: "#fff",
  padding: "2px 5px",
  borderRadius: 3,
  whiteSpace: "nowrap",
};

/** Fixed overlay: edge lines, gutter bands, datum line. */
function FrameOverlay({ m }: { m: FrameMeasurements }) {
  const line = (x: number, colour: string, label: string) => (
    <div
      style={{
        position: "fixed",
        left: x,
        top: 0,
        bottom: 0,
        width: 0,
        borderLeft: `1px dashed ${colour}`,
        pointerEvents: "none",
        zIndex: 900,
      }}
    >
      <div style={{ ...labelStyle, top: m.bodyPadTop - 22, left: 3, color: colour, background: "rgba(0,0,0,0.8)" }}>
        {label}
      </div>
    </div>
  );

  return (
    <>
      {/* gutter bands: center padding on each side */}
      <div
        style={{
          position: "fixed",
          left: m.centerLeft,
          width: m.centerPadLeft,
          top: 0,
          bottom: 0,
          background: GUTTER_COLOUR,
          pointerEvents: "none",
          zIndex: 890,
        }}
      >
        <div style={{ ...labelStyle, top: m.bodyPadTop + 4 }}>{m.centerPadLeft}px</div>
      </div>
      <div
        style={{
          position: "fixed",
          left: m.contentRight,
          width: m.centerPadRight,
          top: 0,
          bottom: 0,
          background: GUTTER_COLOUR,
          pointerEvents: "none",
          zIndex: 890,
        }}
      >
        <div style={{ ...labelStyle, top: m.bodyPadTop + 4 }}>{m.centerPadRight}px</div>
      </div>

      {line(m.contentLeft, EDGE_COLOUR, `content-left ${Math.round(m.contentLeft)}`)}
      {line(m.contentRight, EDGE_COLOUR, `content-right ${Math.round(m.contentRight)}`)}
      {line(Math.min(m.contentLeft + 832, m.contentRight), READING_COLOUR, "reading 832")}

      {/* first-ink datum: horizontal line at the body's top padding */}
      <div
        style={{
          position: "fixed",
          left: 0,
          right: 0,
          top: m.bodyPadTop,
          height: 0,
          borderTop: `1px dashed ${DATUM_COLOUR}`,
          pointerEvents: "none",
          zIndex: 900,
        }}
      >
        <div style={{ ...labelStyle, left: m.contentLeft + 8, top: 3, color: DATUM_COLOUR }}>
          first-ink datum {Math.round(m.bodyPadTop)}px
        </div>
      </div>
    </>
  );
}

/** The live numbers panel — the visible form of __bnLayoutAudit. */
function MeasurementHud({ m }: { m: FrameMeasurements }) {
  const rows: Array<[string, string]> = [
    ["--bn-toolbar-inset", m.toolbarInsetVar],
    ["body padding-top", `${m.bodyPadTop}px`],
    ["body padding-left", `${m.bodyPadLeft}px`],
    ["center gutters", `${m.centerPadLeft} / ${m.centerPadRight}px`],
    ["content edges", `${Math.round(m.contentLeft)} → ${Math.round(m.contentRight)}`],
    ["content width", `${Math.round(m.contentRight - m.contentLeft)}px`],
    ["viewport", `${m.viewportW} × ${m.viewportH}`],
  ];
  return (
    <div
      data-testid="bn-specimen-hud"
      style={{
        position: "fixed",
        right: 12,
        bottom: 44,
        zIndex: 950,
        font: "500 11px/1.5 ui-monospace, monospace",
        background: "rgba(0,0,0,0.82)",
        color: "#e6e6e6",
        borderRadius: 6,
        padding: "8px 10px",
        pointerEvents: "none",
      }}
    >
      {rows.map(([k, v]) => (
        <div key={k}>
          <span style={{ color: "#8ab4ff" }}>{k}</span> {v}
        </div>
      ))}
    </div>
  );
}

/** Radius tier sample row — real tokens, labelled. */
function RadiusTiers() {
  const box = (label: string, radiusVar: string, w: number, h: number) => (
    <div style={{ textAlign: "center" }}>
      <div
        style={{
          width: w,
          height: h,
          borderRadius: `var(${radiusVar})`,
          border: "1px solid var(--bn-colour-border)",
          background: "var(--bn-colour-quote-bg)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          font: "600 11px/1 ui-monospace, monospace",
          color: "var(--bn-colour-muted)",
        }}
      >
        {radiusVar.replace("--bn-radius-", "")}
      </div>
      <div style={{ font: "500 10px/2 ui-monospace, monospace", color: "var(--bn-colour-muted)" }}>{label}</div>
    </div>
  );
  return (
    <div style={{ display: "flex", gap: 24, alignItems: "flex-end", flexWrap: "wrap" }}>
      {box("chip / badge", "--bn-radius-sm", 96, 40)}
      {box("card-in-pane / button", "--bn-radius-md", 120, 64)}
      {box("pane", "--bn-radius-lg", 160, 90)}
      {box("half-height pill", "--bn-radius-pill", 96, 24)}
    </div>
  );
}

/** Static quote-card specimens using the production classes. */
function QuoteSpecimens() {
  const card = (time: string, text: string, badges: React.ReactNode) => (
    <blockquote className="quote-card">
      <div className="quote-row">
        <span className="timecode">[{time}]</span>
        <div className="quote-body">
          <span>“{text}”</span>
        </div>
      </div>
      <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6 }}>{badges}</div>
    </blockquote>
  );
  return (
    <div className="quote-group">
      {card(
        "08:27",
        "I've got here... these... categorizations that I can go to but... that's probably quite busy. Specimen copy at natural quote length to exercise the responsive grid.",
        <>
          <span className="badge badge-ai">Confusion</span>
          <span className="badge badge-user">testtest</span>
        </>,
      )}
      {card(
        "09:10",
        "The obvious thing to pick here is kitchenware and tableware.",
        <>
          <span className="badge badge-ai">Confidence</span>
          <span className="badge badge-user">natural language</span>
        </>,
      )}
      {card(
        "11:00",
        "That's interesting because that's exactly what I want to do. A mid-length specimen so three cards show three different heights in the grid.",
        <span className="badge badge-ai">Satisfaction</span>,
      )}
    </div>
  );
}

/** Minimal signal-card specimens using the production classes. */
function SignalSpecimens() {
  const card = (section: string, title: string, pattern: "tension" | "success") => (
    <div className="signal-card" style={{ ["--card-accent" as string]: "var(--bn-colour-border)" }}>
      <div style={{ font: "600 10px/1.4 ui-monospace, monospace", color: "var(--bn-colour-muted)", textTransform: "uppercase" }}>
        {section}
      </div>
      <h3 style={{ margin: "2px 0 8px" }}>{title}</h3>
      <span className={`pattern-label pattern-${pattern}`}>{pattern}</span>
      <div className="signal-card-quotes" style={{ marginTop: 12, padding: 12 }}>
        <span className="timecode">[11:00]</span> Specimen quote inside the nested card — the inner box must
        be less round than its parent (radius nesting rule).
      </div>
    </div>
  );
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(320px, 1fr))", gap: 20 }}>
      {card("Kitchenware Category", "Orientation-Visibility Tension", "tension")}
      {card("Product Detail Page", "Real-world Matching", "success")}
    </div>
  );
}

export function GridSpecimen() {
  const [m, setM] = useState<FrameMeasurements | null>(null);

  const remeasure = useCallback(() => {
    setM(measureFrame());
  }, []);

  useLayoutEffect(() => {
    remeasure();
  }, [remeasure]);

  useEffect(() => {
    window.addEventListener("resize", remeasure);
    return () => window.removeEventListener("resize", remeasure);
  }, [remeasure]);

  return (
    <div data-testid="bn-grid-specimen">
      {m && <FrameOverlay m={m} />}
      {m && <MeasurementHud m={m} />}

      <h1>Specimen</h1>
      <p className="description">
        Test content on a visible grid. Magenta lines are the content edges; the cyan bands are the
        centre gutters; the green line is the first-ink datum; amber is the 832px reading width. The
        HUD (bottom right) shows the live frame numbers — the same values the layout audit reports.
      </p>

      <h1 className="section-heading">Type</h1>
      <h1>Heading one — lens title size</h1>
      <h2>Heading two — section title with its keyline</h2>
      <h3>Heading three — card / group title</h3>
      <p className="description">
        Body copy at reading width. The paragraph should wrap at the amber line, never at the magenta
        one — if it doesn't, either the max-width token or this page is wrong, and the point of this
        lens is that you can see which.
      </p>

      <h1 className="section-heading">Quote cards</h1>
      <QuoteSpecimens />

      <h1 className="section-heading">Signal cards</h1>
      <SignalSpecimens />

      <h1 className="section-heading">Radius tiers</h1>
      <RadiusTiers />
    </div>
  );
}
