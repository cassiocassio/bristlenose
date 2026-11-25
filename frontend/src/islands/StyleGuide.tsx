/**
 * StyleGuide — the design system, drawn by the code that ships.
 *
 * Dev-only surface, in the family of /report/specimen and
 * /report/picker-specimen: route always registered at /report/style-guide,
 * lazy-loaded, aliased out of the export build (`vite.export.config.ts` →
 * `pages/specimenTabs.export.tsx`) so its fixtures never reach an exported
 * report, and reachable on the Mac from Diagnostics ▸ Style Guide.
 * English-only by design (a dev tool): this file imports no i18n of its own;
 * the components it draws speak the app's locale as they do anywhere.
 *
 * The rule (the owner's, 25 Nov 2026): "only create examples that directly use
 * the exact current codepath to the design system". Every specimen is a
 * shipped component on fixture props, or a token read from the loaded theme
 * CSS. It replaces `docs/design-system/style-guide.html`, whose hand-copied CSS
 * drifted from the app's.
 *
 * Themes are document-level, as in the app. Dark mode lives on `:root` in the
 * theme CSS (`[data-theme="dark"]:root { color-scheme: dark }`, and the
 * `:root:not([data-theme…])` OS fallbacks), so a panel cannot be honestly dark
 * on a light page. The controls set the `<html>` attributes through the same
 * functions the app uses (`applyTheme`, `applyBootPalette`), and the matrix
 * draws each combination as its own document: an iframe of this route.
 *
 * URL: ?palette=<name>&appearance=auto|light|dark&platform=web|desktop
 *      &view=matrix  (the iframes)   &frame=1&section=<id>  (one iframe's body)
 * A parameter left out leaves that attribute as the app set it. `platform`
 * changes the CSS (tokens-desktop.css keys on the attribute); JS that asked
 * `isDesktop()` at boot keeps its answer, so the whole desktop truth is the
 * Mac app itself.
 *
 * Sections are CSF modules (`styleGuide/csf.ts`, listed in
 * `styleGuide/sections.ts`), so Storybook could index them later.
 */

import { useLayoutEffect, useMemo } from "react";
import { useSearchParams } from "react-router-dom";

import { PanelErrorBoundary } from "../components/PanelErrorBoundary";
import { applyTheme, isAppearance, type Appearance } from "../utils/appearance";
import { PALETTES, applyBootPalette, isPalette } from "../utils/bootPalette";
import { sectionId, storiesOf, type SpecimenModule } from "./styleGuide/csf";
import { SECTIONS, SIBLING_PAGES } from "./styleGuide/sections";
import "./styleGuide/styleGuide.css";

type Platform = "web" | "desktop";

interface Theme {
  palette: string | null;
  appearance: Appearance | null;
  platform: Platform | null;
}

function readTheme(params: URLSearchParams): Theme {
  const p = params.get("palette");
  const a = params.get("appearance");
  const f = params.get("platform");
  return {
    palette: isPalette(p) ? p : null,
    appearance: isAppearance(a) ? a : null,
    platform: f === "web" || f === "desktop" ? f : null,
  };
}

/** Set the `<html>` attributes the theme asks for, and put back what was there
 *  when the page goes, so leaving the style guide leaves the app as it was. */
function useDocumentTheme({ palette, appearance, platform }: Theme): void {
  useLayoutEffect(() => {
    const root = document.documentElement;
    const before = {
      palette: root.getAttribute("data-color-theme"),
      theme: root.getAttribute("data-theme"),
      scheme: root.style.colorScheme,
      platform: root.getAttribute("data-platform"),
    };
    const apply = () => {
      if (palette && root.getAttribute("data-color-theme") !== palette) {
        applyBootPalette(root, { getItem: () => palette });
      }
      if (appearance && (root.getAttribute("data-theme") ?? "auto") !== appearance) applyTheme(appearance);
      if (platform === "desktop" && root.getAttribute("data-platform") !== "desktop") {
        root.setAttribute("data-platform", "desktop");
      }
      if (platform === "web" && root.hasAttribute("data-platform")) root.removeAttribute("data-platform");
    };
    apply();
    // Settings' General section is mounted (closed) in every report, and when
    // its lazy chunk lands it applies the SAVED appearance, after this effect
    // (measured 25 Nov 2026: it removed `data-theme="dark"` a moment after we
    // set it). While the style guide is open its theme wins: put it back
    // whenever something else rewrites one of these attributes. `apply` writes
    // only what differs, so its own writes end the loop.
    const mo = new MutationObserver(apply);
    mo.observe(root, { attributes: true, attributeFilter: ["data-color-theme", "data-theme", "data-platform"] });
    return () => {
      mo.disconnect();
      const put = (name: string, v: string | null) =>
        v === null ? root.removeAttribute(name) : root.setAttribute(name, v);
      put("data-color-theme", before.palette);
      put("data-theme", before.theme);
      put("data-platform", before.platform);
      root.style.colorScheme = before.scheme;
    };
  }, [palette, appearance, platform]);
}

function Section({ mod }: { mod: SpecimenModule }) {
  const meta = mod.default;
  const id = sectionId(meta);
  return (
    <section className="bn-sg-section" id={id} data-testid={`bn-sg-section-${id}`}>
      <h2 className="bn-sg-section-title">{meta.title.replace("/", " / ")}</h2>
      {meta.description && <p className="bn-sg-note">{meta.description}</p>}
      {meta.caveat && <p className="bn-sg-note bn-sg-caveat">{meta.caveat}</p>}
      {storiesOf(mod).map(({ key, story }) => (
        <div className="bn-sg-story" key={key} data-testid={`bn-sg-story-${id}-${key}`}>
          <h3 className="bn-sg-story-title">{story.name ?? key}</h3>
          <div className="bn-sg-canvas">
            <PanelErrorBoundary part>{() => story.render()}</PanelErrorBoundary>
          </div>
        </div>
      ))}
    </section>
  );
}

const MATRIX: Array<{ palette: string; appearance: Appearance }> = [
  { palette: "default", appearance: "light" },
  { palette: "default", appearance: "dark" },
  { palette: "edo", appearance: "light" },
  { palette: "edo", appearance: "dark" },
];

function Matrix({ section, platform }: { section: string; platform: Platform | null }) {
  return (
    <div className="bn-sg-matrix" data-testid="bn-sg-matrix">
      {MATRIX.map(({ palette, appearance }) => {
        const q = new URLSearchParams({ frame: "1", palette, appearance, section });
        if (platform) q.set("platform", platform);
        const label = `${palette === "edo" ? "Edo" : "Default"}, ${appearance}`;
        return (
          <figure key={label} className="bn-sg-matrix-cell">
            <figcaption className="bn-sg-note">{label}</figcaption>
            <iframe title={`Style guide, ${label}`} src={`/report/style-guide?${q.toString()}`} />
          </figure>
        );
      })}
    </div>
  );
}

function Controls({ params, setParams }: { params: URLSearchParams; setParams: (p: URLSearchParams) => void }) {
  const set = (name: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(name, value);
    else next.delete(name);
    setParams(next);
  };
  const select = (name: string, label: string, options: readonly string[]) => (
    <label className="bn-sg-control">
      {label}
      <select value={params.get(name) ?? ""} onChange={(e) => set(name, e.target.value)} data-testid={`bn-sg-${name}`}>
        <option value="">as the app set it</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </label>
  );
  const matrix = params.get("view") === "matrix";
  return (
    <div className="bn-sg-controls">
      {select("palette", "Palette", PALETTES)}
      {select("appearance", "Appearance", ["auto", "light", "dark"])}
      {select("platform", "Platform", ["web", "desktop"])}
      <label className="bn-sg-control">
        <input type="checkbox" checked={matrix} onChange={(e) => set("view", e.target.checked ? "matrix" : "")} data-testid="bn-sg-view-matrix" />
        Matrix (Default and Edo, light and dark)
      </label>
      {matrix && (
        <label className="bn-sg-control">
          Section
          <select value={params.get("section") ?? sectionId(SECTIONS[0].default)} onChange={(e) => set("section", e.target.value)}>
            {SECTIONS.map((m) => (
              <option key={sectionId(m.default)} value={sectionId(m.default)}>
                {m.default.title}
              </option>
            ))}
          </select>
        </label>
      )}
    </div>
  );
}

export function StyleGuide() {
  const [params, setParams] = useSearchParams();
  const theme = useMemo(() => readTheme(params), [params]);
  useDocumentTheme(theme);

  const frame = params.get("frame") === "1";
  const section = params.get("section");
  const shown = section ? SECTIONS.filter((m) => sectionId(m.default) === section) : SECTIONS;

  // A matrix frame is a whole report document; bring its section to the top
  // so the specimen, not the report header, fills the frame.
  useLayoutEffect(() => {
    if (frame && section) document.getElementById(section)?.scrollIntoView({ block: "start" });
  }, [frame, section]);

  if (frame) {
    return (
      <div className="bn-sg" data-testid="bn-style-guide" data-frame="">
        {shown.map((m) => (
          <Section key={m.default.title} mod={m} />
        ))}
      </div>
    );
  }

  const matrix = params.get("view") === "matrix";
  return (
    <div className="bn-sg" data-testid="bn-style-guide">
      <header className="bn-sg-header">
        <h1>Style guide</h1>
        <p className="bn-sg-note">
          Every example here is drawn by the shipped components and the loaded theme CSS, on fixture
          data. Nothing is copied. Tags have their own page; so do the picker and the layout grid:
        </p>
        <ul className="bn-sg-links">
          {SIBLING_PAGES.map((p) => (
            <li key={p.href}>
              <a href={p.href}>{p.label}</a> <span className="bn-sg-note">({p.note})</span>
            </li>
          ))}
        </ul>
        <Controls params={params} setParams={(p) => setParams(p, { replace: true })} />
        {!matrix && (
          <nav className="bn-sg-index" aria-label="Style guide sections">
            {SECTIONS.map((m) => (
              <a key={m.default.title} href={`#${sectionId(m.default)}`}>
                {m.default.title}
              </a>
            ))}
          </nav>
        )}
      </header>
      {matrix ? (
        <Matrix section={section ?? sectionId(SECTIONS[0].default)} platform={theme.platform} />
      ) : (
        SECTIONS.map((m) => <Section key={m.default.title} mod={m} />)
      )}
    </div>
  );
}
