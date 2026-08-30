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
import { CodebookV2Page, type PageBook } from "./CodebookV2Page";

interface Props {
  projectId: string;
  refreshKey?: number;
  projectName?: string;
}

/**
 * Built-ins live under "Default"; everything else under "Frameworks" (D17).
 *
 * Derived from the **absence of an author**, not a hardcoded id list. Measured
 * across the nine shipped codebooks: the three built-ins (sentiment, uxr,
 * cli-ux) have no author and all six frameworks have one, so the signal is
 * exact and it is already on the wire. A hardcoded list would have filed the
 * fourth built-in under Frameworks, silently, and nothing would have failed.
 *
 * The limit, stated: a community submission with no author would land under
 * Default. That is wrong but not dangerous, and it becomes real only when the
 * public library accepts submissions — at which point `TemplateOut` should
 * carry the fact rather than have it inferred.
 */
const isBuiltIn = (author: string) => !author.trim();

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
  if (!isBuiltIn(author)) return { text: author, isPerson: true };
  // Sentiment arrives applied; the other built-ins ship with the product but
  // are yours to install and enable. UXR is commonly installed *and disabled*,
  // which "On by default" would misdescribe.
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

  const { rows: books, builtins } = useMemo((): {
    rows: RailBook[];
    builtins: Set<string>;
  } => {
    if (!codebook) return { rows: [], builtins: new Set() };
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
    const builtins = new Set<string>();
    for (const [fid, acc] of byFramework) {
      const tpl = titles.get(fid);
      const author = tpl?.author ?? "";
      if (isBuiltIn(author)) builtins.add(fid);
      const prov = provenanceFor(fid, author);
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
    return { rows, builtins };
  }, [codebook, templates, states, projectName]);

  const onToggle = useCallback((id: string, enabled: boolean) => {
    // Optimistic: the switch is the researcher's statement, not a request for
    // permission. A failure re-reads rather than silently reverting.
    setStates((prev) => ({ ...prev, [id]: enabled }));
    putFrameworkStates({ [id]: enabled }).catch(() => {
      getFrameworkStates().then(setStates).catch(() => {});
    });
  }, []);

  const current = books.find((b) => b.id === selected) ?? books[0];
  const currentGroups = useMemo(
    () =>
      (codebook?.groups ?? []).filter((g) =>
        current?.floor ? !g.framework_id : g.framework_id === current?.id,
      ),
    [codebook, current],
  );

  const page: PageBook | null = current
    ? {
        ...current,
        installed: true,
        quotes: codebook?.framework_quote_totals?.[current.id] ?? 0,
        template: templates?.templates.find((t) => t.id === current.id),
      }
    : null;

  return (
    <div data-testid="bn-codebook-v2">
      <section>
        {/* The zone title and its datum. Browse Library lives HERE, not on the
            page: D22 makes it the unconditional route to the catalogue — with
            the rail closed it is the only way to reach another codebook — so it
            must not come and go with the selection. */}
        <div className="section-heading">
          <h1>Codebook</h1>
          <div className="section-heading-action">
            <button
              className="bn-btn bn-btn-secondary bn-btn-lg"
              data-testid="bn-v2-browse"
              onClick={() => setSelected(selected)}
            >
              Browse Library
            </button>
          </div>
        </div>
        {error && <p className="pg-stat">Could not load the codebook: {error}</p>}
        <div className="v2-layout">
          <CodebookV2Rail
            books={books}
            selectedId={current?.id ?? ""}
            onSelect={setSelected}
            onToggle={onToggle}
            builtinIds={builtins}
          />
          {page && (
            <div className="v2-main">
              <CodebookV2Page
                book={page}
                groups={currentGroups}
                onReview={() => {
                  // Q15: the threshold review stays the EXISTING modal. Phase 5
                  // wires it; opening a half-built one would be worse than not
                  // opening it, and rebuilding it is explicitly ruled out.
                }}
                onInstall={() => {}}
                onUninstall={() => {}}
              />
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
