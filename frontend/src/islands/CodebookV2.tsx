/**
 * Codebook v2 — the lens. Phases 0 (seam) and 2 (rail).
 *
 * Runs beside the shipped `CodebookPanel` rather than replacing it (**D29**);
 * see `docs/design-codebook-v2-plan.md` for the phase order and why the seam
 * came before any component.
 *
 * Data, not chrome, first: everything the rail renders is real. The one field
 * the design wants and the wire lacks is `version` (**Q6**) — the YAML parses
 * it already, so it is plumbing rather than a question.
 */

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getCodebook,
  getCodebookTemplates,
  getFrameworkStates,
  putFrameworkStates,
} from "../utils/api";
import type { CodebookResponse, TemplateListResponse } from "../utils/types";
import { CodebookV2Rail, type RailBook } from "./CodebookV2Rail";

interface Props {
  projectId: string;
  refreshKey?: number;
  projectName?: string;
}

/** Built-ins live under "Default"; everything else under "Frameworks" (D17). */
const BUILTIN_IDS = new Set(["sentiment", "uxr", "cliux"]);

/**
 * Where a codebook came from (**D23**). A framework's provenance is a person; a
 * built-in's is that it shipped with us — and the browse grid is flat, so the
 * rail's "Default" heading cannot carry that for a card.
 *
 * `On by default` for sentiment, which arrives applied. `Available by default`
 * for the rest, which ship with the product but are yours to install and
 * enable. The distinction is not cosmetic: UXR is installed *and disabled* in
 * the common case, which "On by default" would misdescribe.
 */
function provenanceFor(
  id: string,
  author: string,
): { text: string; isPerson: boolean } {
  if (author) return { text: author, isPerson: true };
  if (!BUILTIN_IDS.has(id)) return { text: "", isPerson: false };
  return id === "sentiment"
    ? { text: "On by default", isPerson: false }
    : { text: "Available by default", isPerson: false };
}

export function CodebookV2({ projectId, refreshKey, projectName }: Props) {
  const [codebook, setCodebook] = useState<CodebookResponse | null>(null);
  const [templates, setTemplates] = useState<TemplateListResponse | null>(null);
  const [states, setStates] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    Promise.all([getCodebook(), getCodebookTemplates(), getFrameworkStates()])
      .then(([cb, tpl, st]) => {
        if (!live) return;
        setCodebook(cb);
        setTemplates(tpl);
        setStates(st);
      })
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, [projectId, refreshKey]);

  const books = useMemo((): RailBook[] => {
    if (!codebook) return [];
    // The floor is always present and always first — it is the researcher's own
    // tags, not a codebook they installed (D20).
    const rows: RailBook[] = [
      {
        id: "",
        title: projectName ? `${projectName} tags` : "Your tags",
        provenance: "",
        provenanceIsPerson: false,
        floor: true,
        enabled: true,
        pending: 0,
      },
    ];
    // Installed-only (D17): a framework is in the rail when it has groups in
    // this project, which is exactly what "installed" means.
    const byFramework = new Map<string, { pending: number }>();
    for (const g of codebook.groups) {
      if (!g.framework_id) continue;
      const acc = byFramework.get(g.framework_id) ?? { pending: 0 };
      for (const t of g.tags) acc.pending += t.tentative_count ?? 0;
      byFramework.set(g.framework_id, acc);
    }
    const titles = new Map(
      (templates?.templates ?? []).map((t) => [t.id, t]),
    );
    for (const [fid, acc] of byFramework) {
      const tpl = titles.get(fid);
      const prov = provenanceFor(fid, tpl?.author ?? "");
      rows.push({
        id: fid,
        title: tpl?.title ?? fid,
        provenance: prov.text,
        provenanceIsPerson: prov.isPerson,
        floor: false,
        // Absent from the states map means enabled — "off means off" is stored,
        // "on" is the absence of an off.
        enabled: states[fid] !== false,
        pending: acc.pending,
      });
    }
    return rows;
  }, [codebook, templates, states, projectName]);

  const onToggle = useCallback((id: string, enabled: boolean) => {
    // Optimistic: the switch is the researcher's statement, not a request for
    // permission. A failure re-reads rather than silently reverting.
    setStates((prev) => ({ ...prev, [id]: enabled }));
    putFrameworkStates({ [id]: enabled }).catch(() => {
      getFrameworkStates().then(setStates).catch(() => {});
    });
  }, []);

  return (
    <div className="contentinner" data-testid="bn-codebook-v2">
      <section>
        <div className="section-heading">
          <h1>Codebook</h1>
        </div>
        {error && <p className="pg-stat">Could not load the codebook: {error}</p>}
        <CodebookV2Rail
          books={books}
          selectedId={selected}
          onSelect={setSelected}
          onToggle={onToggle}
          builtinIds={BUILTIN_IDS}
        />
      </section>
    </div>
  );
}
