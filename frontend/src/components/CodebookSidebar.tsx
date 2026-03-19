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
import { apiGet, getCodebook, getCodebookTemplates } from "../utils/api";

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

// ── Component ──────────────────────────────────────────────────────

export function CodebookSidebar() {
  const [projectName, setProjectName] = useState<string | null>(null);
  const [builtIn, setBuiltIn] = useState<CodebookEntry[]>([]);
  const [frameworks, setFrameworks] = useState<CodebookEntry[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);

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

        for (const t of templates) {
          const entry: CodebookEntry = {
            id: t.id,
            label: t.title,
            imported: importedFwIds.has(t.id),
            anchorId: `codebook-fw-${t.id}`,
          };
          if (t.author === "") {
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

  const handleBrowseClick = useCallback(() => {
    window.dispatchEvent(new CustomEvent("bn:codebook-browse"));
  }, []);

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

  // ── Loading state ────────────────────────────────────────────────

  if (projectName === null) return null;

  // ── Render ───────────────────────────────────────────────────────

  return (
    <nav aria-label="Codebooks">
      <div className="toc-heading">Your tags</div>
      <a
        href="#codebook-project"
        className={`toc-link${activeId === "project" ? " active" : ""}`}
        aria-current={activeId === "project" ? "location" : undefined}
        onClick={handleProjectClick}
      >
        {projectName}
      </a>

      {builtIn.length > 0 && (
        <>
          <div className="toc-heading">Built-in</div>
          {builtIn.map((entry) =>
            entry.imported ? (
              <a
                key={entry.id}
                href={`#${entry.anchorId}`}
                className={`toc-link${activeId === entry.id ? " active" : ""}`}
                aria-current={activeId === entry.id ? "location" : undefined}
                onClick={(e) => handleImportedClick(e, entry)}
              >
                {entry.label}
              </a>
            ) : (
              <a
                key={entry.id}
                href="#"
                className="toc-link not-imported"
                onClick={(e) => handleNotImportedClick(e, entry)}
                title={`Browse ${entry.label}`}
              >
                {entry.label}
              </a>
            ),
          )}
        </>
      )}

      {frameworks.length > 0 && (
        <>
          <div className="toc-heading">Frameworks</div>
          {frameworks.map((entry) =>
            entry.imported ? (
              <a
                key={entry.id}
                href={`#${entry.anchorId}`}
                className={`toc-link${activeId === entry.id ? " active" : ""}`}
                aria-current={activeId === entry.id ? "location" : undefined}
                onClick={(e) => handleImportedClick(e, entry)}
              >
                {entry.label}
              </a>
            ) : (
              <a
                key={entry.id}
                href="#"
                className="toc-link not-imported"
                onClick={(e) => handleNotImportedClick(e, entry)}
                title={`Browse ${entry.label}`}
              >
                {entry.label}
              </a>
            ),
          )}
          <button
            className="sidebar-mini-btn"
            type="button"
            onClick={handleBrowseClick}
          >
            Browse codebooks &rarr;
          </button>
        </>
      )}
    </nav>
  );
}
