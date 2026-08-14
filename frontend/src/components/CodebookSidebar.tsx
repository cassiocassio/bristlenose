/**
 * CodebookSidebar — codebook-level navigation for the left sidebar.
 *
 * Three sections: "Your tags" (project), "Built-in" (Bristlenose),
 * "Frameworks" (academic). One entry per codebook (not per group).
 * Imported codebooks scroll to the relevant section in CodebookPanel.
 * Not-imported codebooks open the browse modal via custom event.
 *
 * Active state is "last clicked" — no scroll spy (CodebookPanel uses
 * a horizontal grid, not vertical scroll).
 *
 * @module CodebookSidebar
 */

import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { apiGet, getCodebook, getCodebookTemplates } from "../utils/api";
import {
  hydrateFrameworkStates,
  useSidebarStore,
} from "../contexts/SidebarStore";
import { codebookDotState } from "../utils/codebookDot";

// ── Types ──────────────────────────────────────────────────────────

interface ProjectInfo {
  project_name: string;
  session_count: number;
  participant_count: number;
}

interface CodebookEntry {
  /** Unique key — "project" or template ID. */
  id: string;
  label: string;
  imported: boolean;
  /** Anchor ID in CodebookPanel to scroll to. */
  anchorId: string;
}

// ── Status dot ─────────────────────────────────────────────────────

/** A single blue/grey/transparent status dot, first-line aligned. Blue = on,
 * grey = disabled, transparent = available (slot reserved so text left-edges
 * align) or floor (no switch). Purely decorative — the label carries meaning. */
function CodebookDot({ state }: { state?: "on" | "off" | "available" }) {
  const modifier = state === "on" || state === "off" ? ` codebook-dot-${state}` : "";
  return <span className={`codebook-dot${modifier}`} aria-hidden="true" />;
}

// ── Component ──────────────────────────────────────────────────────

export function CodebookSidebar() {
  const { t } = useTranslation();
  const [projectName, setProjectName] = useState<string | null>(null);
  const [builtIn, setBuiltIn] = useState<CodebookEntry[]>([]);
  const [frameworks, setFrameworks] = useState<CodebookEntry[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

  // Framework enable/disable state drives the status dot (blue on / grey off).
  const { disabledFrameworks } = useSidebarStore();

  // Hydrate the persisted disabled set once per session (guarded in the store,
  // so this is a no-op if TagSidebar / CodebookPanel already hydrated it).
  useEffect(() => {
    hydrateFrameworkStates();
  }, []);

  // ── Data fetching ──────────────────────────────────────────────

  const fetchData = useCallback(() => {
    // Fetch project name (same pattern as Header.tsx)
    apiGet<ProjectInfo>("/info")
      .then((info) => setProjectName(info.project_name))
      .catch(() => setProjectName("Project"));

    // Fetch codebook + templates to determine which are imported
    Promise.all([getCodebook(), getCodebookTemplates()])
      .then(([codebook, templateResp]) => {
        const templates = templateResp.templates;

        // Determine which framework IDs are imported (have groups)
        const importedFwIds = new Set(
          codebook.groups
            .map((g) => g.framework_id)
            .filter((fid): fid is string => fid != null),
        );

        // Split templates: built-in (author === "") vs frameworks (author !== "")
        const builtInEntries: CodebookEntry[] = [];
        const frameworkEntries: CodebookEntry[] = [];

        for (const tmpl of templates) {
          const entry: CodebookEntry = {
            id: tmpl.id,
            label: tmpl.id === "sentiment" ? t("codebook.sentimentTitle") : tmpl.title,
            imported: importedFwIds.has(tmpl.id),
            anchorId: `codebook-fw-${tmpl.id}`,
          };
          if (tmpl.author === "") {
            builtInEntries.push(entry);
          } else {
            frameworkEntries.push(entry);
          }
        }

        setBuiltIn(builtInEntries);
        setFrameworks(frameworkEntries);
      })
      .catch((err) => console.error("CodebookSidebar: fetch failed", err));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ── Refresh on codebook changes (e.g. after import/remove) ──────

  useEffect(() => {
    const handler = () => fetchData();
    window.addEventListener("codebook-changed", handler);
    return () => window.removeEventListener("codebook-changed", handler);
  }, [fetchData]);

  // ── Default active entry: first imported codebook ────────────────

  useEffect(() => {
    if (activeId !== null) return;
    // Default to "project" (researcher's own tags are always present)
    setActiveId("project");
  }, [activeId, builtIn, frameworks]);

  // ── Click handlers ───────────────────────────────────────────────

  const handleImportedClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>, entry: CodebookEntry) => {
      e.preventDefault();
      setActiveId(entry.id);
      const el = document.getElementById(entry.anchorId);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
    [],
  );

  const handleNotImportedClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>, template: CodebookEntry) => {
      e.preventDefault();
      window.dispatchEvent(
        new CustomEvent("bn:codebook-browse", {
          detail: { templateId: template.id },
        }),
      );
    },
    [],
  );

  // Removed 14 Aug 2026 with the "Codebook Library →" button below — the same
  // string is already a primary button in the Codebooks panel header, so this
  // duplicated an affordance visible on the same screen. Browsing stays
  // reachable three ways: that panel button, clicking a not-imported row here,
  // and the native Browse Codebooks… menu item. A more natural entry point is
  // round 2. To restore, uncomment this and the button in the render.
  // const handleBrowseClick = useCallback(() => {
  //   window.dispatchEvent(new CustomEvent("bn:codebook-browse"));
  // }, []);

  const handleProjectClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>) => {
      e.preventDefault();
      setActiveId("project");
      const el = document.getElementById("codebook-project");
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    },
    [],
  );

  // ── Row renderer (shared by built-in + frameworks) ───────────────

  const renderEntry = (entry: CodebookEntry) => {
    const dotState = codebookDotState(entry.imported, entry.id, disabledFrameworks);
    if (entry.imported) {
      const isActive = activeId === entry.id;
      return (
        <a
          key={entry.id}
          href={`#${entry.anchorId}`}
          className={`toc-link codebook-toc-link${dotState === "off" ? " codebook-disabled" : ""}${isActive ? " active" : ""}`}
          aria-current={isActive ? "location" : undefined}
          onClick={(e) => handleImportedClick(e, entry)}
        >
          <CodebookDot state={dotState} />
          <span className="codebook-toc-label">{entry.label}</span>
        </a>
      );
    }
    return (
      // <a href="#"> is a JS action, not navigation; native Enter
      // activation on the anchor handles keyboard.
      // eslint-disable-next-line jsx-a11y/anchor-is-valid
      <a
        key={entry.id}
        href="#"
        className="toc-link codebook-toc-link not-imported"
        onClick={(e) => handleNotImportedClick(e, entry)}
        title={`Browse ${entry.label}`}
      >
        <CodebookDot state={dotState} />
        <span className="codebook-toc-label">{entry.label}</span>
      </a>
    );
  };

  // ── Loading state ────────────────────────────────────────────────

  if (projectName === null) return null;

  // ── Render ───────────────────────────────────────────────────────

  return (
    <nav aria-label={t("nav.codebook")}>
      <div className="toc-heading">{t("codebook.yourTags")}</div>
      <a
        href="#codebook-project"
        className={`toc-link codebook-toc-link${activeId === "project" ? " active" : ""}`}
        aria-current={activeId === "project" ? "location" : undefined}
        onClick={handleProjectClick}
      >
        {/* Floor codebook: no switch, so no dot — a bare slot keeps its label
            left-edge aligned with the toggleable codebooks below. */}
        <CodebookDot />
        <span className="codebook-toc-label">{projectName}</span>
      </a>

      {builtIn.length > 0 && (
        <>
          <div className="toc-heading">{t("codebook.builtIn")}</div>
          {builtIn.map(renderEntry)}
        </>
      )}

      {frameworks.length > 0 && (
        <>
          <div className="toc-heading">{t("codebook.frameworks")}</div>
          {frameworks.map(renderEntry)}
          {/* Removed 14 Aug 2026 — see the handleBrowseClick note above.
              <button
                className="sidebar-mini-btn"
                type="button"
                onClick={handleBrowseClick}
              >
                {t("codebook.browseCodebooks")} &rarr;
              </button> */}
        </>
      )}
    </nav>
  );
}
