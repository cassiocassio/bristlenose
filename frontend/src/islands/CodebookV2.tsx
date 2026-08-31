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
  removeCodebookFramework,
  startAutoCode,
} from "../utils/api";
import { addJob } from "../contexts/ActivityStore";
import type {
  CodebookResponse,
  RemoveFrameworkInfo,
  TemplateListResponse,
} from "../utils/types";
// The navigator moved OUT of this lens and into the standard left sidebar
// (`components/CodebookV2Sidebar`), which `AppLayout` renders as a sibling —
// so the selection can no longer be component state. Both sides read the store.
import {
  resetCodebookV2Selection,
  selectCodebookV2,
  useCodebookV2Store,
} from "../contexts/CodebookV2Store";
import { CodebookV2Page, type PageBook } from "./CodebookV2Page";
// By path, not the barrel — see the note in CodebookPanel.tsx.
import { SectionHeading } from "../components/SectionHeading";
import { CodebookV2Browse, type BrowseBook } from "./CodebookV2Browse";
import { CodebookV2UninstallSheet } from "../components/CodebookV2UninstallSheet";
// Q15: the threshold review is the EXISTING modal, not a v2 rebuild. Imported
// by path rather than through the `components` barrel for the same reason as
// CodebookAuthoring below — the barrel rides in the always-loaded chunk and
// this lens is lazy.
import { ThresholdReviewModal } from "../components/ThresholdReviewModal";
// By path, not through the `components` barrel — see CodebookPanel.tsx.
import { MergeConfirm } from "../components/CodebookAuthoring";
import { useCodebookAuthoring } from "../hooks/useCodebookAuthoring";
import { isExportMode } from "../utils/exportData";

/** What the page needs to know about one codebook. Was `RailBook`, which
 *  belonged to the in-lens rail; the navigator now lives in the sidebar and
 *  derives its own rows from the wire. */
interface LensBook {
  /** `framework_id`, or `""` for the floor. */
  id: string;
  title: string;
  provenance: string;
  provenanceIsPerson: boolean;
  floor: boolean;
  enabled: boolean;
  pending: number;
}

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
  const { selectedId: selected } = useCodebookV2Store();
  const setSelected = selectCodebookV2;
  // Two views, no third. D22: a codebook is reached by a rail row or by a card,
  // and Browse Library is the only route to the catalogue — no next/previous,
  // no traversal. With the rail closed it is the ONLY way to another codebook,
  // which is why its prominence is load-bearing rather than decorative.
  const [view, setView] = useState<"page" | "browse">("page");
  // Module-level state outlives the component; reset it so a later visit starts
  // on the floor rather than on whichever framework was last inspected.
  useEffect(() => resetCodebookV2Selection, []);

  // Selecting in the navigator leaves the catalogue. The rail used to do this
  // itself, in the same handler as the selection; with the two split across a
  // store, choosing a codebook while the Library was open would otherwise
  // change the selection behind a grid that stayed on screen — a click that
  // appears to do nothing.
  useEffect(() => {
    setView("page");
  }, [selected]);

  // Uninstall is confirmed, never immediate. D20 option A made it destroy the
  // AutoCode run as well as the tags, so the sheet has more to say than the
  // shipped one — and a terse modal measures rather than warning.
  // Read-only is a property of the artefact, not a preference: an exported
  // report is a file someone was handed.
  const readOnly = isExportMode();
  // `impactFailed` is a THIRD state, not a nicety: `impact === null` alone
  // cannot distinguish "still counting" from "the count failed", and the sheet
  // rendered both as "nothing is lost" — a reassurance on a destructive path
  // that we had not measured.
  const [pendingUninstall, setPendingUninstall] = useState<{
    id: string;
    title: string;
    impact: RemoveFrameworkInfo | null;
    impactFailed?: boolean;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Same shape the shipped lens uses (`CodebookPanel`'s `reportModal`), because
  // it feeds the same component.
  const [reportModal, setReportModal] = useState<{
    frameworkId: string;
    frameworkTitle: string;
  } | null>(null);

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

  const { rows: books } = useMemo((): { rows: LensBook[] } => {
    if (!codebook) return { rows: [] };
    // The floor is always present and always first — it is the researcher's own
    // tags, not a codebook they installed (D20).
    const rows: LensBook[] = [
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
      const author = tpl?.author ?? "";
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
    return { rows };
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

  // The switch lives in the sidebar now, and the page's knocked-back treatment
  // follows it. The sidebar fires `codebook-changed` after a successful write —
  // the event the shipped lens already uses — so the page refreshes rather than
  // showing an enabled framework as off, or the reverse.
  useEffect(() => {
    const handler = () => reload();
    window.addEventListener("codebook-changed", handler);
    return () => window.removeEventListener("codebook-changed", handler);
  }, [reload]);

  // The activity chip dispatches this when the researcher clicks View Report,
  // and it dispatches IN PLACE when they are already on a codebook lens — so
  // v2 has to answer it, exactly as CodebookPanel does, or the chip's action
  // would silently do nothing here.
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.frameworkId && detail?.frameworkTitle) {
        setReportModal({
          frameworkId: detail.frameworkId,
          frameworkTitle: detail.frameworkTitle,
        });
      }
    };
    window.addEventListener("bn:autocode-report", handler);
    return () => window.removeEventListener("bn:autocode-report", handler);
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
            // Two lenses run side by side, and the chip's "View Report" used to
            // send everyone to the shipped one. Say where this started.
            originRoute: "/report/codebook-v2/",
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
      .catch(() =>
        // NOT a silent catch. The sheet has to say it does not know, because
        // the alternative is telling the researcher nothing will be lost when
        // we never found out.
        setPendingUninstall((p) =>
          p && p.id === id ? { ...p, impactFailed: true } : p,
        ),
      );
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


  const current = books.find((b) => b.id === selected) ?? books[0];
  const currentGroups = useMemo(
    () =>
      (codebook?.groups ?? [])
        .filter((g) =>
          current?.floor ? !g.framework_id : g.framework_id === current?.id,
        )
        // The shipped lens's comparator, verbatim (CodebookPanel: `sortedGroups`).
        // Uncategorised leads because it is where an untagged quote lands, and a
        // researcher needs to see it without hunting. v2 did no sorting at all,
        // so it rendered in API order and put Uncategorised LAST — visible the
        // moment the two lenses were opened side by side on the same project,
        // which is what D29 is for. Not new UX to decide; parity we had lost.
        .sort((a, b) => {
          if (a.is_default !== b.is_default) return a.is_default ? -1 : 1;
          return a.order - b.order;
        }),
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
    // A FRAGMENT, not a wrapper div. `report.css` flushes the first zone title
    // to the shared datum with
    // `.center > main > section:first-of-type > .section-heading` — so the
    // <section> has to be a DIRECT child of <main>. v2 wrapped everything in a
    // `<div data-testid>`, which made the section a grandchild, so the selector
    // never matched, `margin-top: 0` never applied, and this lens sat lower
    // than every other one. A fragment renders no node, so the path holds and
    // the testid moves onto the section itself.
    <>
      <section data-testid="bn-codebook-v2">
        {/* The zone title and its datum. Rendered through `SectionHeading`, not
            a hand-typed `.section-heading` div: that component exists because
            "a class you have to remember to type will eventually be forgotten"
            — written after Codebook's own h1 shipped with no class in three
            render states. v2 typed the class and got the shape right by copy;
            going through the component makes it structural, so a change to the
            zone-title treatment lands here without anyone editing this file.

            Browse Library is the title's `action`, which the component
            right-aligns and bottom-aligns to the keyline. It lives HERE, not on
            the page: D22 makes it the unconditional route to the catalogue —
            with the rail closed it is the only way to reach another codebook —
            so it must not come and go with the selection.

            Q14 — export mode's fourth state: read-only, installed, offline. No
            Browse Library, because there is no catalogue to browse (the
            templates route is server-only) and installing is a write. Passing
            no action is the house pattern; the row's height and the keyline's
            position are identical either way. */}
        <SectionHeading
          action={
            !readOnly ? (
              <button
                className="bn-btn bn-btn-secondary bn-btn-lg"
                data-testid="bn-v2-browse"
                onClick={() => setView("browse")}
              >
                Browse Library
              </button>
            ) : null
          }
        >
          Codebook
        </SectionHeading>
        {error && <p className="pg-stat">Could not load the codebook: {error}</p>}
        {/* No rail here. Codebook navigation is the standard left sidebar
            (`CodebookV2Sidebar`, mounted by AppLayout), which brings the
            toolbar toggle, the `[` key, drag-to-resize, hover-peek and the
            `panel-state` bridge post with it — none of which an in-lens rail
            could have. */}
        <div className="v2-layout">
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
                onReview={() =>
                  setReportModal({
                    frameworkId: page.id,
                    frameworkTitle: page.title,
                  })
                }
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
      {/* Q15 — the shipped threshold review, unchanged. `onApply` mirrors
          `CodebookPanel.handleReportApply`: close, refetch, and tell the other
          islands that tags moved, since a bulk apply changes what QuoteSections
          renders. */}
      <ThresholdReviewModal
        open={reportModal !== null}
        frameworkId={reportModal?.frameworkId ?? ""}
        frameworkTitle={reportModal?.frameworkTitle ?? ""}
        onClose={() => setReportModal(null)}
        onApply={() => {
          setReportModal(null);
          reload();
          document.dispatchEvent(new CustomEvent("bn:tags-changed"));
        }}
      />
      {pendingUninstall && (
        <CodebookV2UninstallSheet
          title={pendingUninstall.title}
          impact={pendingUninstall.impact}
          impactFailed={pendingUninstall.impactFailed ?? false}
          onCancel={() => setPendingUninstall(null)}
          onConfirm={onConfirmUninstall}
        />
      )}
    </>
  );
}
