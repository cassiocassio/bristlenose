/**
 * KeylineLab — tune the dashed keyline of a tentative (AutoCode-proposed) tag.
 *
 * The rule (the owner's, 25 Nov 2026): every example and every handle drives
 * the exact current code path. So nothing here draws a tag. The tags are the
 * shipped `Badge` (one tentative tag on every codebook fill) and the whole Tag
 * specimen (`TagSpecimen`: QuoteCard, the sidebar, the Codebook, the review
 * dialog) on its fixtures; the handles retune the shipped rules themselves, in
 * the loaded theme stylesheet, through the CSSOM (`keylineLab/themeRules.ts`),
 * and put them back when the page goes. Each handle is one value in
 * `atoms/badge.css` or `molecules/threshold-review.css` (`keylineLab/spec.ts`),
 * and the page prints the chosen values as CSS to drop into those two files.
 * Colour-lab pattern: retune here, then change both the CSS and `SHIPPED`.
 *
 * Why a sibling of /report/tag-specimen and not handles on it: the specimen is
 * the catalogue of what ships, and this page rewrites the shipped rules while
 * it is open. Kept apart, the catalogue never shows a value that has not shipped.
 *
 * Light and dark, and shipped against the lab, are iframes of this route
 * (`?frame=1`), because dark mode is `:root`-bound in the theme CSS: a panel
 * cannot honestly be dark on a light page (as the style guide's matrix).
 *
 * URL: ?k=<spec JSON>&appearance=auto|light|dark&palette=<name>
 *      &frame=1&pulse=pulse|calm   (one comparison frame)
 * Route always registered at /report/keyline-lab and lazy-loaded; kept out of
 * the HTML export (vite.export.config.ts). English-only by design (a dev tool).
 */

import { lazy, Suspense, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Badge } from "../components/Badge";
import { setPulse } from "../contexts/AutoCodePlayback";
import { applyTheme, isAppearance, type Appearance } from "../utils/appearance";
import { PALETTES, applyBootPalette, isPalette } from "../utils/bootPalette";
import { COLOUR_SETS, getTagBg } from "../utils/colours";
import { reading, resolve, surround, type Reading, type Rgba } from "./keylineLab/contrast";
import {
  DEFAULT_ENV,
  SHIPPED,
  dropInCss,
  isShipped,
  lineOf,
  num,
  parseSpec,
  ruleEdits,
  type Env,
  type Keyline,
  type LabSpec,
} from "./keylineLab/spec";
import { ThemeRuleEditor } from "./keylineLab/themeRules";
import "./keylineLab/keylineLab.css";

const TagSpecimen = lazy(() => import("./TagSpecimen").then((m) => ({ default: m.TagSpecimen })));

const noop = () => {};
const MESSAGE = "bn-keyline-lab";
type Pulse = "still" | "pulse" | "calm";

// ── The document's theme (as the style guide sets it) ─────────────────

/** Force the appearance and palette the lab asks for, through the app's own functions,
 *  and put back what was there when the page goes. Settings' General section re-applies
 *  the SAVED appearance when its chunk lands (style guide, 25 Nov 2026), so reassert. */
function useDocumentTheme(appearance: Appearance | null, palette: string | null): void {
  useLayoutEffect(() => {
    if (!appearance && !palette) return;
    const root = document.documentElement;
    const before = { theme: root.getAttribute("data-theme"), palette: root.getAttribute("data-color-theme"), scheme: root.style.colorScheme };
    const apply = () => {
      if (palette && root.getAttribute("data-color-theme") !== palette) applyBootPalette(root, { getItem: () => palette });
      if (appearance && (root.getAttribute("data-theme") ?? "auto") !== appearance) applyTheme(appearance);
    };
    apply();
    const mo = new MutationObserver(apply);
    mo.observe(root, { attributes: true, attributeFilter: ["data-theme", "data-color-theme"] });
    return () => {
      mo.disconnect();
      const put = (name: string, v: string | null) => (v === null ? root.removeAttribute(name) : root.setAttribute(name, v));
      put("data-theme", before.theme);
      put("data-color-theme", before.palette);
      root.style.colorScheme = before.scheme;
    };
  }, [appearance, palette]);
}

// ── Readouts ──────────────────────────────────────────────────────────

function lineColour(el: Element, line: Keyline): Rgba | null {
  return line.technique === "drawn"
    ? resolve(getComputedStyle(el, "::before").backgroundColor)
    : resolve(getComputedStyle(el).borderTopColor);
}

function readEl(el: Element, line: Keyline, opacity: number): Reading | null {
  const ink = lineColour(el, line);
  const fill = resolve(getComputedStyle(el).backgroundColor);
  const page = surround(el);
  if (!ink || !fill || !page) return null;
  return reading(ink, fill, page, opacity);
}

function fmt(r: Reading | null): string {
  return r ? `fill ${r.onFill.toFixed(1)} · page ${r.onPage.toFixed(1)}` : "no canvas";
}

/** The least contrast across `els` at one opacity: the fill that reads worst decides. */
function worst(els: Element[], line: Keyline, opacity: number): string {
  const rs = els.map((el) => readEl(el, line, opacity)).filter((r): r is Reading => r !== null);
  if (rs.length === 0) return els.length === 0 ? "none drawn" : "no canvas";
  const f = Math.min(...rs.map((r) => r.onFill));
  const p = Math.min(...rs.map((r) => r.onPage));
  return `${f.toFixed(2)} on fill · ${p.toFixed(2)} on page`;
}

function measure(root: HTMLElement, spec: LabSpec): void {
  const q = spec.quote;
  for (const el of Array.from(root.querySelectorAll<HTMLElement>("[data-kl-swatch] .badge-proposed"))) {
    const out = el.closest("[data-kl-swatch]")?.querySelector("[data-kl-reading]");
    if (out) out.textContent = fmt(readEl(el, q.line, q.rest));
  }
  const quoteEls = Array.from(root.querySelectorAll(".badge-proposed"));
  const rowEls = Array.from(root.querySelectorAll(".threshold-tag-tentative"));
  const counterEls = Array.from(root.querySelectorAll(".threshold-zone-counter--tentative"));
  const cells: Record<string, string> = {
    "quote-rest": worst(quoteEls, q.line, q.rest),
    "quote-trough": worst(quoteEls, q.line, q.trough),
    "quote-peak": worst(quoteEls, q.line, q.peak),
    "quote-hover": worst(quoteEls, q.line, q.hover),
    "row-rest": worst(rowEls, lineOf(spec, "row"), 1),
    "counter-trough": worst(counterEls, lineOf(spec, "counter"), spec.counter.trough),
    "counter-peak": worst(counterEls, lineOf(spec, "counter"), spec.counter.peak),
  };
  for (const [key, text] of Object.entries(cells)) {
    const cell = root.querySelector(`[data-kl-cell="${key}"]`);
    if (cell) cell.textContent = text;
  }
}

/** Retune the shipped rules to `spec`; restore them when the page goes. Writes the
 *  readouts and any rule it could not find straight into the DOM after layout. */
function useThemeEdits(
  spec: LabSpec | null,
  root: React.RefObject<HTMLElement | null>,
  ready: number,
) {
  const editor = useRef<ThemeRuleEditor | null>(null);
  const [env] = useState<Env>(() => {
    const r = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--bn-radius-sm"));
    return Number.isFinite(r) ? { radius: r } : DEFAULT_ENV;
  });
  useLayoutEffect(() => {
    editor.current ??= new ThemeRuleEditor();
    // null: the shipped theme as loaded, untouched (a comparison frame's "Shipped").
    const lost = spec ? editor.current.apply(ruleEdits(spec, env)) : [];
    const el = root.current;
    if (!el) return;
    const warn = el.querySelector<HTMLElement>("[data-kl-missing]");
    if (warn) {
      warn.hidden = lost.length === 0;
      warn.textContent = `The lab could not find these shipped rules, so it is not retuning them: ${lost.join(", ")}`;
    }
    measure(el, spec ?? SHIPPED);
  }, [spec, env, root, ready]);
  useEffect(() => () => editor.current?.restore(), []);
  return env;
}

// ── Handles ───────────────────────────────────────────────────────────

function Slider({ label, css, value, min, max, step, onChange, testId }: {
  label: string;
  css: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (v: number) => void;
  testId: string;
}) {
  return (
    <label className="bn-kl-handle" title={css}>
      <span>{label}</span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} data-testid={testId} />
      <output>{num(value)}</output>
    </label>
  );
}

function Choice<T extends string>({ label, css, value, options, onChange, testId }: {
  label: string;
  css: string;
  value: T;
  options: Array<[T, string]>;
  onChange: (v: T) => void;
  testId: string;
}) {
  return (
    <label className="bn-kl-handle" title={css} style={{ gridTemplateColumns: "5.5rem minmax(0, 1fr)" }}>
      <span>{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value as T)} data-testid={testId}>
        {options.map(([v, text]) => (
          <option key={v} value={v}>
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

function LineHandles({ line, onChange, id }: { line: Keyline; onChange: (l: Keyline) => void; id: string }) {
  const set = <K extends keyof Keyline>(k: K, v: Keyline[K]) => onChange({ ...line, [k]: v });
  const drawn = line.technique === "drawn";
  return (
    <>
      <Choice
        label="Technique"
        css="border-style, or a masked ::before for Drawn"
        value={line.technique}
        options={[["dashed", "Dashed (CSS border)"], ["dotted", "Dotted (CSS border)"], ["drawn", "Drawn dash (SVG mask)"], ["solid", "Solid (reference)"]]}
        onChange={(v) => set("technique", v)}
        testId={`bn-kl-${id}-technique`}
      />
      <Slider label="Width px" css="border-width, or the SVG stroke" value={line.width} min={0.5} max={2} step={0.25} onChange={(v) => set("width", v)} testId={`bn-kl-${id}-width`} />
      {drawn && (
        <>
          <Slider label="Dash px" css="stroke-dasharray, first value" value={line.dash} min={0} max={8} step={0.5} onChange={(v) => set("dash", v)} testId={`bn-kl-${id}-dash`} />
          <Slider label="Gap px" css="stroke-dasharray, second value" value={line.gap} min={0.5} max={8} step={0.5} onChange={(v) => set("gap", v)} testId={`bn-kl-${id}-gap`} />
          <Choice label="Ends" css="stroke-linecap" value={line.cap} options={[["butt", "Square"], ["round", "Round (0 dash = dots)"]]} onChange={(v) => set("cap", v)} testId={`bn-kl-${id}-cap`} />
        </>
      )}
      <Choice
        label="Ink"
        css="border-color, or the ::before background"
        value={line.ink}
        options={[["current", "currentColor (the tag's text)"], ["text", "--bn-colour-text"], ["muted", "--bn-colour-muted"], ["accent", "--bn-colour-accent"], ["border", "--bn-colour-border"]]}
        onChange={(v) => set("ink", v)}
        testId={`bn-kl-${id}-ink`}
      />
      <Slider label="Strength %" css="color-mix(ink N%, transparent)" value={line.strength} min={0} max={100} step={5} onChange={(v) => set("strength", v)} testId={`bn-kl-${id}-strength`} />
    </>
  );
}

function Handles({ spec, onChange }: { spec: LabSpec; onChange: (s: LabSpec) => void }) {
  const q = spec.quote;
  const setQ = (patch: Partial<LabSpec["quote"]>) => onChange({ ...spec, quote: { ...q, ...patch } });
  const setRow = (patch: Partial<LabSpec["row"]>) => onChange({ ...spec, row: { ...spec.row, ...patch } });
  const setCounter = (patch: Partial<LabSpec["counter"]>) => onChange({ ...spec, counter: { ...spec.counter, ...patch } });
  return (
    <aside className="bn-kl-handles" aria-label="Keyline handles" data-testid="bn-kl-handles">
      <fieldset>
        <legend>Tentative tag</legend>
        <p className="bn-kl-note">
          <code>.badge-proposed</code>, atoms/badge.css: quote cards, Screens.
        </p>
        <LineHandles line={q.line} onChange={(line) => setQ({ line })} id="quote" />
        <Slider label="At rest" css=".badge-proposed opacity, and the keyframe's still point" value={q.rest} min={0.3} max={1} step={0.01} onChange={(rest) => setQ({ rest })} testId="bn-kl-quote-rest" />
        <Slider label="Pulse low" css="bn-proposed-breathe 0%/100% at depth 1" value={q.trough} min={0.2} max={1} step={0.01} onChange={(trough) => setQ({ trough })} testId="bn-kl-quote-trough" />
        <Slider label="Pulse high" css="bn-proposed-breathe 50% at depth 1" value={q.peak} min={0.2} max={1} step={0.01} onChange={(peak) => setQ({ peak })} testId="bn-kl-quote-peak" />
        <Slider label="Hover" css=".badge-proposed:hover opacity (!important)" value={q.hover} min={0.3} max={1} step={0.01} onChange={(hover) => setQ({ hover })} testId="bn-kl-quote-hover" />
      </fieldset>
      <fieldset>
        <legend>Review row tag</legend>
        <p className="bn-kl-note">
          <code>.badge.threshold-tag-tentative</code>: full opacity and no pulse, by decision (24 Nov 2026).
        </p>
        <label className="bn-kl-check">
          <input type="checkbox" checked={spec.row.linked} onChange={(e) => setRow({ linked: e.target.checked, line: q.line })} data-testid="bn-kl-row-linked" />
          Same keyline as the tentative tag
        </label>
        {!spec.row.linked && <LineHandles line={spec.row.line} onChange={(line) => setRow({ line })} id="row" />}
      </fieldset>
      <fieldset>
        <legend>Review counter</legend>
        <p className="bn-kl-note">
          <code>.threshold-zone-counter--tentative</code>: pulses whenever the dialog is open.
        </p>
        <label className="bn-kl-check">
          <input type="checkbox" checked={spec.counter.linked} onChange={(e) => setCounter({ linked: e.target.checked, line: q.line })} data-testid="bn-kl-counter-linked" />
          Same keyline as the tentative tag
        </label>
        {!spec.counter.linked && <LineHandles line={spec.counter.line} onChange={(line) => setCounter({ line })} id="counter" />}
        <Slider label="Pulse low" css="bn-proposed-pulse 0%/100%" value={spec.counter.trough} min={0.2} max={1} step={0.01} onChange={(trough) => setCounter({ trough })} testId="bn-kl-counter-trough" />
        <Slider label="Pulse high" css="bn-proposed-pulse 50%" value={spec.counter.peak} min={0.2} max={1} step={0.01} onChange={(peak) => setCounter({ peak })} testId="bn-kl-counter-peak" />
      </fieldset>
      <button type="button" className="bn-btn bn-btn-secondary" onClick={() => onChange(SHIPPED)} data-testid="bn-kl-reset">
        Back to shipped
      </button>
    </aside>
  );
}

// ── Specimens ─────────────────────────────────────────────────────────

/** One tentative tag on every codebook fill: the shipped Badge, as QuoteCard draws it. */
function Swatches() {
  return (
    <div className="bn-kl-swatches" data-testid="bn-kl-swatches">
      {Object.entries(COLOUR_SETS).map(([set, { slots }], row) => (
        <div key={set} style={{ display: "contents" }}>
          <span className="bn-kl-note" style={{ gridColumn: 1, gridRow: row + 1 }}>
            {set}
          </span>
          {Array.from({ length: slots }, (_, i) => (
            <div key={i} className="bn-kl-swatch" data-kl-swatch="" style={{ gridColumn: i + 2, gridRow: row + 1 }}>
              <Badge text={`${set} ${i + 1}`} variant="proposed" colour={getTagBg(set, i)} onAccept={noop} onDeny={noop} />
              <span className="bn-kl-reading" data-kl-reading="" />
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function ContrastTable() {
  const row = (label: string, key: string) => (
    <tr>
      <th scope="row">{label}</th>
      <td data-kl-cell={key} />
    </tr>
  );
  return (
    <table className="bn-kl-table" data-testid="bn-kl-contrast">
      <thead>
        <tr>
          <th scope="col">Where, and when</th>
          <th scope="col">Least contrast of the keyline, across every fill drawn</th>
        </tr>
      </thead>
      <tbody>
        {row("Tentative tag, at rest", "quote-rest")}
        {row("Tentative tag, pulse low", "quote-trough")}
        {row("Tentative tag, pulse high", "quote-peak")}
        {row("Tentative tag, hovered", "quote-hover")}
        {row("Review row tag", "row-rest")}
        {row("Review counter, pulse low", "counter-trough")}
        {row("Review counter, pulse high", "counter-peak")}
      </tbody>
    </table>
  );
}

function Compare({ spec, palette, pulse }: { spec: LabSpec; palette: string | null; pulse: Pulse }) {
  const frames = useRef<Array<HTMLIFrameElement | null>>([]);
  // Each frame loads once with the spec of the moment; later changes are posted, so a
  // dragged slider does not reload four documents.
  const [initial] = useState(() => ({ spec, pulse }));
  const post = (f: HTMLIFrameElement | null) =>
    f?.dataset.lab === "1" && f.contentWindow?.postMessage({ type: MESSAGE, spec, pulse }, window.location.origin);
  useEffect(() => {
    frames.current.forEach(post);
  });
  const cells: Array<{ lab: boolean; appearance: Appearance }> = [
    { lab: false, appearance: "light" },
    { lab: true, appearance: "light" },
    { lab: false, appearance: "dark" },
    { lab: true, appearance: "dark" },
  ];
  return (
    <div className="bn-kl-compare" data-testid="bn-kl-compare">
      {cells.map(({ lab, appearance }, i) => {
        const q = new URLSearchParams({ frame: "1", appearance });
        if (palette) q.set("palette", palette);
        if (lab) q.set("k", JSON.stringify(initial.spec));
        if (initial.pulse !== "still") q.set("pulse", initial.pulse);
        const label = `${lab ? "Lab" : "Shipped"}, ${appearance}`;
        return (
          <figure key={label}>
            <figcaption className="bn-kl-note">{label}</figcaption>
            <iframe
              ref={(f) => {
                frames.current[i] = f;
              }}
              data-lab={lab ? "1" : "0"}
              title={`Keyline lab, ${label}`}
              src={`/report/keyline-lab?${q.toString()}`}
              onLoad={(e) => post(e.currentTarget)}
            />
          </figure>
        );
      })}
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────

function Specimens({ ready }: { ready: () => void }) {
  return (
    <>
      <section className="bn-kl-section" id="bn-kl-swatches">
        <h2>Every codebook fill</h2>
        <p className="bn-kl-note">
          The shipped <code>Badge</code>, tentative, on each codebook's fills. Under each: the keyline's contrast
          at rest against the tag's fill and against what it sits on (WCAG ratio; 3 is the non-text reference).
        </p>
        <Swatches />
      </section>
      <Suspense fallback={null}>
        <SpecimenLoaded onReady={ready} />
      </Suspense>
    </>
  );
}

function SpecimenLoaded({ onReady }: { onReady: () => void }) {
  useEffect(() => {
    onReady();
  }, [onReady]);
  return <TagSpecimen />;
}

function Frame() {
  const [params] = useSearchParams();
  const [spec, setSpec] = useState(() => parseSpec(params.get("k")));
  const [pulse, setPulseState] = useState<Pulse>(() => {
    const p = params.get("pulse");
    return p === "pulse" || p === "calm" ? p : "still";
  });
  const shipped = params.get("k") === null;
  const root = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(0);
  const onReady = useMemo(() => () => setReady((n) => n + 1), []);
  const appearance = params.get("appearance");
  const palette = params.get("palette");
  useDocumentTheme(isAppearance(appearance) ? appearance : null, isPalette(palette) ? palette : null);
  // A shipped frame retunes nothing: the theme as loaded.
  useThemeEdits(shipped ? null : spec, root, ready);

  useEffect(() => {
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== window.location.origin || e.data?.type !== MESSAGE) return;
      if (!shipped) setSpec(parseSpec(JSON.stringify(e.data.spec)));
      const p = e.data.pulse;
      setPulseState(p === "pulse" || p === "calm" ? p : "still");
    };
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, [shipped]);
  // After TagSpecimen's own mount effect (which stills the pulse), so this one wins.
  useEffect(() => {
    setPulse(pulse === "still" ? null : pulse);
  }, [pulse, ready]);
  useEffect(() => () => setPulse(null), []);
  // Bring the swatches to the top of the frame. Not scrollIntoView: that scrolls every
  // scrollable ancestor, the parent page included.
  useLayoutEffect(() => {
    const el = document.getElementById("bn-kl-swatches");
    if (el) window.scrollTo(0, el.getBoundingClientRect().top + window.scrollY);
  }, [ready]);

  return (
    <div className="bn-kl" data-frame="" ref={root} data-testid="bn-keyline-lab">
      <p className="bn-kl-warn" data-kl-missing="" hidden />
      <Specimens ready={onReady} />
    </div>
  );
}

export function KeylineLab() {
  const [params, setParams] = useSearchParams();
  if (params.get("frame") === "1") return <Frame />;
  return <Lab params={params} setParams={setParams} />;
}

function Lab({ params, setParams }: { params: URLSearchParams; setParams: ReturnType<typeof useSearchParams>[1] }) {
  const k = params.get("k");
  const spec = useMemo(() => parseSpec(k), [k]);
  const appearance = params.get("appearance");
  const palette = params.get("palette");
  const [pulse, setComparePulse] = useState<Pulse>("still");
  const root = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(0);
  const onReady = useMemo(() => () => setReady((n) => n + 1), []);
  useDocumentTheme(isAppearance(appearance) ? appearance : null, isPalette(palette) ? palette : null);
  const env = useThemeEdits(spec, root, ready);

  const set = (name: string, value: string | null) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    setParams(next, { replace: true });
  };
  const css = dropInCss(spec, env);
  const unchanged = isShipped(spec);

  return (
    <div className="bn-kl" ref={root} data-testid="bn-keyline-lab">
      <Handles spec={spec} onChange={(s) => set("k", isShipped(s) ? null : JSON.stringify(s))} />
      <div>
        <h1>Keyline lab</h1>
        <p className="bn-kl-note">
          The dashed outline that says "the machine suggested this; you haven't decided". Every tag here is a
          shipped component on fixture data; the handles retune the shipped rules in the loaded theme while this
          page is open, and put them back when it closes. Hover a tag for its hover state; the Tag specimen's
          Pulse, Calm and Still buttons below drive the pulse.
        </p>
        <p className="bn-kl-warn" data-kl-missing="" hidden data-testid="bn-kl-missing" />
        <div style={{ display: "flex", flexWrap: "wrap", gap: "var(--bn-space-md)", margin: "var(--bn-space-md) 0" }}>
          <label className="bn-kl-check">
            Appearance
            <select value={appearance ?? ""} onChange={(e) => set("appearance", e.target.value || null)} data-testid="bn-kl-appearance">
              <option value="">as the app set it</option>
              <option value="light">light</option>
              <option value="dark">dark</option>
            </select>
          </label>
          <label className="bn-kl-check">
            Palette
            <select value={palette ?? ""} onChange={(e) => set("palette", e.target.value || null)} data-testid="bn-kl-palette">
              <option value="">as the app set it</option>
              {PALETTES.map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
        </div>

        <section className="bn-kl-section">
          <h2>Contrast</h2>
          <ContrastTable />
          <p className="bn-kl-note">
            The formula's figure for a pixel the line covers fully. A 0.5px line on a 1x screen, and a dash's
            antialiased ends, draw lighter: check those in the screenshots.
          </p>
        </section>

        <Specimens ready={onReady} />

        <section className="bn-kl-section">
          <h2>Shipped against the lab, light and dark</h2>
          <label className="bn-kl-check">
            Frames show
            <select value={pulse} onChange={(e) => setComparePulse(e.target.value as Pulse)} data-testid="bn-kl-compare-pulse">
              <option value="still">still (at rest)</option>
              <option value="pulse">the pulse</option>
              <option value="calm">calm</option>
            </select>
          </label>
          <Compare spec={spec} palette={isPalette(palette) ? palette : null} pulse={pulse} />
        </section>

        <section className="bn-kl-section">
          <h2>{unchanged ? "CSS (the shipped values; nothing changed)" : "CSS to drop in"}</h2>
          <button type="button" className="bn-btn bn-btn-secondary" onClick={() => void navigator.clipboard?.writeText(css)} data-testid="bn-kl-copy">
            Copy
          </button>
          <pre className="bn-kl-css" data-testid="bn-kl-css">
            {css}
          </pre>
        </section>
      </div>
    </div>
  );
}
