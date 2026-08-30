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
  getRemoveFrameworkImpact,
  importCodebookTemplate,
  putFrameworkStates,
  removeCodebookFramework,
  startAutoCode,
} from "../utils/api";
import { addJob } from "../contexts/ActivityStore";
import type {
  CodebookResponse,
  RemoveFrameworkInfo,
  TemplateListResponse,
} from "../utils/types";
import { CodebookV2Rail, type RailBook } from "./CodebookV2Rail";
import { CodebookV2Page, type PageBook } from "./CodebookV2Page";
import { CodebookV2Browse, type BrowseBook } from "./CodebookV2Browse";
import { CodebookV2UninstallSheet } from "../components/CodebookV2UninstallSheet";
// By path, not through the `components` barrel — see CodebookPanel.tsx.
import { MergeConfirm } from "../components/CodebookAuthoring";
import { useCodebookAuthoring } from "../hooks/useCodebookAuthoring";
import { isExportMode } from "../utils/exportData";

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
  // Null offline: the catalogue is server-only, and the lens degrades to the
  // codebook it can read rather than failing.
  const [templates, setTemplates] = useState<TemplateListResponse | null>(null);
  const [states, setStates] = useState<Record<string, boolean>>({});
  const [selected, setSelected] = useState("");
  // Two views, no third. D22: a codebook is reached by a rail row or by a card,
  // and Browse Library is the only route to the catalogue — no next/previous,
  // no traversal. With the rail closed it is the ONLY way to another codebook,
  // which is why its prominence is load-bearing rather than decorative.
  const [view, setView] = useState<"page" | "browse">("page");
  // Uninstall is confirmed, never immediate. D20 option A made it destroy the
  // AutoCode run as well as the tags, so the sheet has more to say than the
  // shipped one — and a terse modal measures rather than warning.
  // Read-only is a property of the artefact, not a preference: an exported
  // report is a file someone was handed.
  const readOnly = isExportMode();
  const [pendingUninstall, setPendingUninstall] = useState<{
    id: string;
    title: string;
    impact: RemoveFrameworkInfo | null;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let live = true;
    // `/codebook` and `/framework-states` are EMBEDDED in an export;
    // `/codebook/templates` is SERVER_ONLY (routes/export.py), so offline it
    // throws. A bare Promise.all rejects on that one and blanks the whole lens
    // — the reader of a leave-behind would get an error where their codebook
    // should be. Tolerated separately: the catalogue is unavailable offline,
    // the codebook itself is not.
    Promise.all([
      getCodebook(),
      getCodebookTemplates().catch(() => null),
      getFrameworkStates(),
    ])
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

  const reload = useCallback(() => {
    Promise.all([getCodebook(), getCodebookTemplates(), getFrameworkStates()])
      .then(([cb, tpl, st]) => {
        setCodebook(cb);
        setTemplates(tpl);
        setStates(st);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  const onInstall = useCallback(
    (id: string, title: string) => {
      // **Install IS apply** (D4), and that is two calls, not one. Importing the
      // template alone would put the tags in the codebook and code nothing —
      // which is precisely the separate-Apply-step v2 exists to remove, left
      // half-implemented and therefore invisible.
      //
      // No confirmation, deliberately: it spends, but the researcher asked by
      // clicking, and a dialog on an additive act teaches them to dismiss
      // dialogs — which is what makes the destructive one stop working.
      importCodebookTemplate(id)
        .then(() => startAutoCode(id))
        .then(() => {
          // Register with the activity store so the chip stack shows progress.
          // Autotagging is not instant; without this the researcher clicks
          // Install and nothing appears to happen for minutes.
          addJob(`autocode:${id}`, {
            type: "autocode",
            frameworkId: id,
            frameworkTitle: title,
          });
          reload();
        })
        .catch((e: Error) => setError(e.message));
    },
    [reload],
  );

  const onAskUninstall = useCallback((id: string, title: string) => {
    setPendingUninstall({ id, title, impact: null });
    // The counts arrive after the sheet, so it opens instantly and fills in.
    // Blocking on the fetch would make a destructive confirmation feel laggy,
    // which is the wrong thing to teach about it.
    getRemoveFrameworkImpact(id)
      .then((impact) =>
        setPendingUninstall((p) => (p && p.id === id ? { ...p, impact } : p)),
      )
      .catch(() => {});
  }, []);

  const onConfirmUninstall = useCallback(() => {
    const target = pendingUninstall;
    if (!target) return;
    setPendingUninstall(null);
    removeCodebookFramework(target.id)
      .then(reload)
      .catch((e: Error) => setError(e.message));
  }, [pendingUninstall, reload]);

  // The floor's authoring apparatus — the same hook the shipped lens drives, so
  // add/rename/delete/drag/merge are one implementation rather than two that
  // agree today. Every group in the codebook, framework ones included: a new
  // group's colour set is chosen by what is unused, and asking only the groups
  // on screen would hand out one a framework already holds.
  const authoring = useCodebookAuthoring({
    groups: codebook?.groups,
    onChanged: reload,
  });

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

  // The catalogue is every template, installed or not — unlike the rail, which
  // is installed-only (D17). That asymmetry is the point: the rail is what you
  // have, the Library is what there is.
  const browseBooks = useMemo((): BrowseBook[] => {
    const installedIds = new Set(books.filter((b) => !b.floor).map((b) => b.id));
    return (templates?.templates ?? []).map((t) => {
      const prov = provenanceFor(t.id, t.author);
      return {
        id: t.id,
        title: t.title,
        provenance: prov.text,
        provenanceIsPerson: prov.isPerson,
        installed: installedIds.has(t.id),
        enabled: states[t.id] !== false,
        quotes: codebook?.framework_quote_totals?.[t.id] ?? 0,
        tags: t.groups.reduce((n, g) => n + g.tags.length, 0),
        template: t,
      };
    });
  }, [templates, books, states, codebook]);

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
          {/* Q14 — export mode's fourth state: read-only, installed, offline.
              No Browse Library, because there is no catalogue to browse (the
              templates route is server-only) and installing is a write. The
              store-layer gate hides the control rather than disabling it, which
              is the house pattern for export mode. */}
          {!readOnly && (
            <div className="section-heading-action">
              <button
                className="bn-btn bn-btn-secondary bn-btn-lg"
                data-testid="bn-v2-browse"
                onClick={() => setView("browse")}
              >
                Browse Library
              </button>
            </div>
          )}
        </div>
        {error && <p className="pg-stat">Could not load the codebook: {error}</p>}
        <div className="v2-layout">
          <CodebookV2Rail
            books={books}
            selectedId={view === "page" ? (current?.id ?? "") : ""}
            onSelect={(id) => {
              // A rail row is the other route to a codebook, and it leaves the
              // catalogue — otherwise selecting in the rail would silently do
              // nothing while the grid stayed on screen.
              setSelected(id);
              setView("page");
            }}
            onToggle={onToggle}
            builtinIds={builtins}
          />
          {view === "browse" ? (
            <div className="v2-main">
              <CodebookV2Browse
                books={browseBooks}
                onOpen={(id) => {
                  setSelected(id);
                  setView("page");
                }}
                onBack={() => setView("page")}
                onInstall={(id) =>
                  onInstall(
                    id,
                    browseBooks.find((b) => b.id === id)?.title ?? id,
                  )
                }
                onUninstall={(id) =>
                  onAskUninstall(
                    id,
                    browseBooks.find((b) => b.id === id)?.title ?? id,
                  )
                }
              />
            </div>
          ) : page ? (
            <div className="v2-main">
              <CodebookV2Page
                book={page}
                groups={currentGroups}
                authoring={authoring}
                allTagNames={codebook?.all_tag_names ?? []}
                onReview={() => {
                  // Q15: the threshold review stays the EXISTING modal. Phase 5
                  // wires it; opening a half-built one would be worse than not
                  // opening it, and rebuilding it is explicitly ruled out.
                }}
                onInstall={(id) => onInstall(id, page.title)}
                onUninstall={(id) => onAskUninstall(id, page.title)}
                readOnly={readOnly}
              />
            </div>
          ) : null}
        </div>
      </section>
      {/* Merge confirmation — centred over the lens, not inside a card, because
          it names two tags that may sit in different groups. Same component the
          shipped lens renders. */}
      <MergeConfirm
        pending={authoring.pendingMerge}
        onConfirm={authoring.onConfirmMerge}
        onCancel={authoring.onCancelMerge}
      />
      {pendingUninstall && (
        <CodebookV2UninstallSheet
          title={pendingUninstall.title}
          impact={pendingUninstall.impact}
          onCancel={() => setPendingUninstall(null)}
          onConfirm={onConfirmUninstall}
        />
      )}
    </div>
  );
}
