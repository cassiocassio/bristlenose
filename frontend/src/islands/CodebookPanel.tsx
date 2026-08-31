import { Fragment, useCallback, useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import i18n from "../i18n";
import { toast } from "../utils/toast";
import { safeUrlOrNull } from "../utils/safeUrl";
import { autocodeRefusal } from "../utils/autocodeRefusal";
import type { ApiError } from "../utils/api";
import { isExportMode } from "../utils/exportData";
import { ct } from "../utils/platformTranslation";
import { ConfirmDialog, SectionHeading, ThresholdReviewModal } from "../components";
// The floor's authoring apparatus is shared with the v2 lens. It lives in its
// own module, not here, so that there is one implementation of
// add/rename/delete/drag/merge rather than two.
//
// Imported by path rather than through the `components` barrel *deliberately*:
// the barrel rides in the always-loaded chunk, and this apparatus is reachable
// only from two lazy codebook islands. Through the barrel it cost the landing
// route ~7 kB gzipped for markup no first paint renders.
import {
  CodebookGroupColumn,
  MergeConfirm,
  NewGroupPlaceholder,
} from "../components/CodebookAuthoring";
import { useCodebookAuthoring } from "../hooks/useCodebookAuthoring";
import { addJob } from "../contexts/ActivityStore";
import {
  dropFrameworkDisabled,
  hydrateFrameworkStates,
  setFrameworkDisabled,
  useSidebarStore,
} from "../contexts/SidebarStore";
import {
  getAutoCodeStatus,
  getCodebook,
  getCodebookTemplates,
  getRemoveFrameworkImpact,
  importCodebookTemplate,
  removeCodebookFramework,
  startAutoCode,
} from "../utils/api";
import type {
  AutoCodeJobStatus,
  CodebookGroupResponse,
  CodebookResponse,
  RemoveFrameworkInfo,
  TemplateOut,
} from "../utils/types";

// ---------------------------------------------------------------------------
// Colour helpers — shared module (see utils/colours.ts)
// ---------------------------------------------------------------------------

import { getGroupBg, getTagBg } from "../utils/colours";
import { summariseFramework } from "../utils/codebookSummary";

// ---------------------------------------------------------------------------
// Main island
// ---------------------------------------------------------------------------

interface CodebookPanelProps {
  projectId: string;
  /** Bumped by LastRunStore on pipeline completion → re-fetches codebook. */
  refreshKey?: number;
  /** Human project name for the "<project> tags" section header. The page
      (CodebookTab) fetches it from /info and passes it down; absent in the
      legacy island path, where the header falls back to "Your tags". */
  projectName?: string;
}

export function CodebookPanel({ projectId, refreshKey = 0, projectName }: CodebookPanelProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<CodebookResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [modalView, setModalView] = useState<"closed" | "picker" | "preview">("closed");
  const [templates, setTemplates] = useState<TemplateOut[] | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateOut | null>(null);

  // Author links, with anything we would not put in an href dropped. The value
  // is config data: curated YAML today, community-submitted once the public
  // library exists. See utils/safeUrl.ts for the rule and why it is not a
  // dependency. Normalised, not merely checked — a URL that was only safe
  // because the parser stripped a tab out of it must render stripped.
  const safeAuthorLinks = useMemo(
    () =>
      (selectedTemplate?.author_links ?? [])
        .map((link) => ({ label: link.label, href: safeUrlOrNull(link.url) }))
        .filter((link): link is { label: string; href: string } => link.href !== null),
    [selectedTemplate],
  );
  const [importing, setImporting] = useState(false);
  // Per-tile Install/Uninstall busy id, so only the acting tile's button
  // disables while its request is in flight.
  const [pendingTemplateId, setPendingTemplateId] = useState<string | null>(null);
  const [removeConfirm, setRemoveConfirm] = useState<{
    frameworkId: string;
    label: string;
    impact: RemoveFrameworkInfo | null;
  } | null>(null);

  // --- AutoCode state ---
  const [autoCodeStatus, setAutoCodeStatus] = useState<Record<string, AutoCodeJobStatus | null>>({});
  const [reportModal, setReportModal] = useState<{ frameworkId: string; frameworkTitle: string } | null>(null);

  // --- Framework enable/disable (the codebook-lens switch — THE disable control) ---
  // The trailing switch on each framework header turns that codebook off. Disable is
  // FUNCTIONAL — "off means off" (design-codebook-state-model.md §8): the section
  // folds, badges hide report-wide, the codebook drops from the tags sidebar +
  // autocomplete, AND new sessions stop being coded (the re-apply gate reads
  // `enabled`). Applied tags are kept; re-enabling fires a catch-up delta. State
  // lives in SidebarStore (`disabledFrameworks`) as one source of truth, persisted
  // to ProjectFrameworkState via /framework-states.
  const { disabledFrameworks } = useSidebarStore();
  const toggleFramework = useCallback(
    (fid: string, title: string) => {
      const wasDisabled = disabledFrameworks.has(fid);
      const result = setFrameworkDisabled(fid, !wasDisabled);
      if (wasDisabled) {
        // OFF → ON: if the backend kicked off a catch-up (new sessions to code),
        // surface it as an activity chip (numberless; §4a).
        result.then((res) => {
          if (res.catchUp.includes(fid)) {
            addJob(`catchup:${fid}`, {
              type: "catchup",
              frameworkId: fid,
              frameworkTitle: title,
            });
          }
        });
      }
    },
    [disabledFrameworks],
  );

  // Hydrate the persisted disable state once per session (guarded in the store).
  // Deps are [] deliberately: the store's guard makes this a one-shot, and the SPA
  // is one-project-per-page-load (BRISTLENOSE_API_BASE is a fixed window global), so
  // a projectId dep would imply a per-project re-hydrate the guard silently defeats.
  // If in-place project switching is ever added, key the store guard on projectId.
  useEffect(() => {
    hydrateFrameworkStates();
  }, []);

  // Fetch codebook data
  const fetchData = useCallback(() => {
    getCodebook()
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData, projectId, refreshKey]);

  // Re-fetch when a background AutoCode job completes (event dispatched by
  // AppLayout's ActivityChipStack onComplete callback). Refreshes both codebook
  // data (tag counts) and per-framework autocode status (button state).
  useEffect(() => {
    const handler = () => {
      fetchData();
      if (data) {
        for (const g of data.groups) {
          if (g.framework_id) {
            getAutoCodeStatus(g.framework_id)
              .then((status) =>
                setAutoCodeStatus((prev) => ({ ...prev, [g.framework_id!]: status })),
              )
              .catch(() => {});
          }
        }
      }
    };
    window.addEventListener("codebook-changed", handler);
    return () => window.removeEventListener("codebook-changed", handler);
  }, [fetchData, data]);

  // Re-fetch when the codebook tab becomes visible (covers the race where
  // vanilla JS PUT /tags hasn't finished when the panel first mounts).
  useEffect(() => {
    const panel = document.getElementById("bn-codebook-root")?.closest(".bn-tab-panel");
    if (!panel) return;
    const observer = new MutationObserver(() => {
      if (panel.classList.contains("active")) fetchData();
    });
    observer.observe(panel, { attributes: true, attributeFilter: ["class"] });
    return () => observer.disconnect();
  }, [fetchData]);

  // Eagerly fetch templates when codebook data has framework groups,
  // so framework title/author are available for section headers immediately.
  useEffect(() => {
    if (!data) return;
    const hasFrameworks = data.groups.some((g) => g.framework_id != null);
    if (hasFrameworks && !templates) {
      getCodebookTemplates()
        .then((resp) => setTemplates(resp.templates))
        .catch(() => {});
    }
  }, [data, templates]);

  // Poll autocode status for each imported framework on mount.
  useEffect(() => {
    if (!data) return;
    const frameworkIds = new Set<string>();
    for (const g of data.groups) {
      if (g.framework_id) frameworkIds.add(g.framework_id);
    }
    for (const fid of frameworkIds) {
      getAutoCodeStatus(fid)
        .then((status) => {
          setAutoCodeStatus((prev) => ({ ...prev, [fid]: status }));
          // If a job is running, register it in the activity store so the
          // chip stack (rendered in AppLayout) shows progress.
          if (status.status === "running") {
            const tmpl = templates?.find((t) => t.id === fid);
            const title = tmpl?.title ?? fid;
            addJob(`autocode:${fid}`, { type: "autocode", frameworkId: fid, frameworkTitle: title });
          }
        })
        .catch(() => {
          // 404 = no job yet, button should be enabled.
          setAutoCodeStatus((prev) => ({ ...prev, [fid]: null }));
        });
    }
  }, [data, templates]);

  // --- Authoring: add/rename/delete a tag, add/delete a group, drag, merge ---

  // One implementation, shared with the v2 lens (hooks/useCodebookAuthoring).
  // `data?.groups` rather than the researcher groups on screen: a new group's
  // colour set is chosen by what is unused, and a framework's sets count too.
  const authoring = useCodebookAuthoring({ groups: data?.groups, onChanged: fetchData });

  // --- Browse / import handlers ---

  const handleOpenPicker = useCallback(() => {
    setModalView("picker");
    getCodebookTemplates()
      .then((resp) => setTemplates(resp.templates))
      .catch((err) => console.error("Fetch templates failed:", err));
  }, []);

  // Listen for sidebar "browse codebook" requests (CodebookSidebar dispatches this)
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.templateId) {
        // Open picker, then auto-select the requested template
        getCodebookTemplates()
          .then((resp) => {
            setTemplates(resp.templates);
            const tmpl = resp.templates.find(
              (t: TemplateOut) => t.id === detail.templateId,
            );
            if (tmpl) {
              setSelectedTemplate(tmpl);
              setModalView("preview");
            } else {
              setModalView("picker");
            }
          })
          .catch(() => setModalView("picker"));
      } else {
        handleOpenPicker();
      }
    };
    window.addEventListener("bn:codebook-browse", handler);
    return () => window.removeEventListener("bn:codebook-browse", handler);
  }, [handleOpenPicker]);

  // Open the ThresholdReviewModal when the activity chip toast dispatches
  // bn:autocode-report (e.g. user clicks "View Report" on the completion toast).
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.frameworkId && detail?.frameworkTitle) {
        setReportModal({ frameworkId: detail.frameworkId, frameworkTitle: detail.frameworkTitle });
      }
    };
    window.addEventListener("bn:autocode-report", handler);
    return () => window.removeEventListener("bn:autocode-report", handler);
  }, []);

  const handleSelectTemplate = useCallback((t: TemplateOut) => {
    setSelectedTemplate(t);
    setModalView("preview");
  }, []);

  const handleImportTemplate = useCallback(() => {
    if (!selectedTemplate || importing) return;
    setImporting(true);
    importCodebookTemplate(selectedTemplate.id)
      .then((codebook) => {
        setData(codebook);
        setModalView("closed");
        setSelectedTemplate(null);
        // Re-fetch templates to update imported flags
        getCodebookTemplates()
          .then((resp) => setTemplates(resp.templates))
          .catch(() => {});
      })
      .catch((err) => console.error("Import template failed:", err))
      .finally(() => setImporting(false));
  }, [selectedTemplate, importing]);

  const handleCloseModal = useCallback(() => {
    setModalView("closed");
    setSelectedTemplate(null);
  }, []);

  // --- AutoCode handlers ---

  const handleStartAutoCode = useCallback(
    (frameworkId: string, frameworkTitle: string) => {
      startAutoCode(frameworkId)
        .then((status) => {
          setAutoCodeStatus((prev) => ({ ...prev, [frameworkId]: status }));
          addJob(`autocode:${frameworkId}`, { type: "autocode", frameworkId, frameworkTitle });
        })
        .catch((err: ApiError) => {
          // Don't swallow — a failed start (409 already-running, 503 no API key,
          // 400 no quotes) otherwise leaves the button looking like it did nothing.
          console.error("Start AutoCode failed:", err);
          // Localise from the server's stable `reason`, never from `detail`:
          // that string is written for a log and one case tells the reader to
          // run a shell command. Unrecognised reason falls back to the generic
          // sentence rather than leaking developer prose.
          const refusal = autocodeRefusal(err.reason);
          toast(
            refusal?.message ??
              i18n.t("codebook.autoCodeStartFailed", {
                defaultValue: "Couldn't start AutoCode.",
              }),
            4000,
            refusal?.kind ?? "error",
          );
        });
    },
    [],
  );


  const handleOpenReport = useCallback(
    (frameworkId: string, frameworkTitle: string) => {
      setReportModal({ frameworkId, frameworkTitle });
    },
    [],
  );

  const handleReportApply = useCallback(() => {
    setReportModal(null);
    fetchData();
    // Notify other islands (QuoteSections) that tags changed via bulk apply.
    document.dispatchEvent(new CustomEvent("bn:tags-changed"));
  }, [fetchData]);

  // --- Remove framework handlers ---

  const handleAskRemoveFramework = useCallback((frameworkId: string, label: string) => {
    setRemoveConfirm({ frameworkId, label, impact: null });
    getRemoveFrameworkImpact(frameworkId)
      .then((info) => setRemoveConfirm((prev) => prev ? { ...prev, impact: info } : null))
      .catch(() => {});
  }, []);

  // Install a codebook straight from its Library tile (the "Install" side of the
  // per-tile toggle). Reuses the import endpoint; the picker stays open so the
  // tile flips to its "Installed / Uninstall" state in place.
  const handleInstallFromLibrary = useCallback(
    (tmpl: TemplateOut) => {
      if (pendingTemplateId) return;
      setPendingTemplateId(tmpl.id);
      importCodebookTemplate(tmpl.id)
        .then((codebook) => {
          setData(codebook);
          return getCodebookTemplates();
        })
        .then((resp) => setTemplates(resp.templates))
        .catch((err) => console.error("Install template failed:", err))
        .finally(() => setPendingTemplateId(null));
    },
    [pendingTemplateId],
  );

  // Uninstall a codebook from its Library tile (the "Uninstall" side of the
  // toggle). Closes the picker and routes into the existing remove-with-impact
  // confirmation — the same guard the per-framework Uninstall button uses.
  const handleUninstallFromLibrary = useCallback(
    (tmpl: TemplateOut) => {
      const label = tmpl.author ? `${tmpl.author} — ${tmpl.title}` : tmpl.title;
      setModalView("closed");
      handleAskRemoveFramework(tmpl.id, label);
    },
    [handleAskRemoveFramework],
  );

  const handleConfirmRemoveFramework = useCallback(() => {
    if (!removeConfirm) return;
    const fid = removeConfirm.frameworkId;
    removeCodebookFramework(fid)
      .then((codebook) => {
        setData(codebook);
        setRemoveConfirm(null);
        // Uninstall forgets the enable/disable opinion (the server drops its
        // ProjectFrameworkState row). Shed it locally too, so reinstalling a
        // previously-disabled codebook comes back enabled, not folded/greyed.
        dropFrameworkDisabled(fid);
        getCodebookTemplates()
          .then((resp) => setTemplates(resp.templates))
          .catch(() => {});
      })
      .catch((err) => console.error("Remove framework failed:", err));
  }, [removeConfirm]);

  // --- Menu-bar dispatched listeners ---

  // Listen for menu-bar "remove framework" requests (dispatched by AppLayout).
  useEffect(() => {
    const handler = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      const frameworkId = detail?.frameworkId as string | undefined;
      if (!frameworkId || !data) return;
      const tmpl = templates?.find((t) => t.id === frameworkId);
      const label = tmpl?.title ?? frameworkId;
      handleAskRemoveFramework(frameworkId, label);
    };
    window.addEventListener("bn:codebook-remove", handler);
    return () => window.removeEventListener("bn:codebook-remove", handler);
  }, [data, templates, handleAskRemoveFramework]);

  // Listen for menu-bar "create group" requests (dispatched by AppLayout).
  useEffect(() => {
    const handler = () => authoring.onCreateGroup();
    window.addEventListener("bn:codebook-create-group", handler);
    return () => window.removeEventListener("bn:codebook-create-group", handler);
  }, [authoring]);

  // Listen for menu-bar "create code" requests (dispatched by AppLayout).
  // Adds a new tag to the first researcher (non-framework) group.
  useEffect(() => {
    const handler = () => {
      if (!data) return;
      const researcherGroup = data.groups
        .filter((g) => g.framework_id == null)
        .sort((a, b) => (a.is_default === b.is_default ? a.order - b.order : a.is_default ? -1 : 1))[0];
      if (researcherGroup) {
        authoring.groupProps.onCreateTag(i18n.t("codebook.newCode"), researcherGroup.id);
      }
    };
    window.addEventListener("bn:codebook-create-code", handler);
    return () => window.removeEventListener("bn:codebook-create-code", handler);
  }, [data, authoring]);

  // --- Render ---

  if (error) {
    return (
      <section>
        <SectionHeading>{t("codebook.heading")}</SectionHeading>
        <p className="codebook-description">{t("codebook.errorLoading", { error })}</p>
      </section>
    );
  }

  if (!data) {
    return (
      <section>
        <SectionHeading>{t("codebook.heading")}</SectionHeading>
        <p className="codebook-description">{t("labels.loading")}</p>
      </section>
    );
  }

  // Split groups into researcher vs framework
  const sortedGroups = [...data.groups].sort((a, b) => {
    if (a.is_default !== b.is_default) return a.is_default ? -1 : 1;
    return a.order - b.order;
  });
  const researcherGroups = sortedGroups.filter((g) => g.framework_id == null);
  const frameworkGroups = sortedGroups.filter((g) => g.framework_id != null);

  // Group framework groups by framework_id for per-framework sections
  const frameworkById = new Map<string, CodebookGroupResponse[]>();
  for (const g of frameworkGroups) {
    const fid = g.framework_id!;
    if (!frameworkById.has(fid)) frameworkById.set(fid, []);
    frameworkById.get(fid)!.push(g);
  }

  // The Library action rides in the zone title's action slot on the web, and
  // in the native toolbar on desktop (ContentView.swift, the Codebook branch
  // of `toolbarTrailing`) — so `ct()` suppresses the in-pane copy there rather
  // than showing the same action twice on one screen. Same reasoning that
  // retired the sidebar's "Codebook Library →" on 14 Aug 2026.
  const browseLabel = ct(t, "codebook.browseCodebooks");
  const browseAction = browseLabel ? (
    /* codebook-picker-btn is the hook export.css hides on — the picker
       fetches from a server that isn't there in an exported report. */
    <button
      className="bn-btn codebook-picker-btn"
      onClick={handleOpenPicker}
      data-testid="bn-codebook-browse-btn"
    >
      {browseLabel}
    </button>
  ) : null;

  return (
    // Zone title must be a direct child of a <section> that is a direct child
    // of <main> — that is the whole of the flush-to-datum contract in
    // templates/report.css (`.center > main > section:first-of-type >
    // .section-heading`), and it is how Quotes and Sessions land on the datum.
    // Codebook rendered a bare fragment until 20 Aug 2026, so the selector
    // never matched and this lens opened 40px lower than the other three. The
    // rule needed no widening; this lens needed enrolling. Same reason
    // SessionsTable.tsx carries the identical comment.
    <section>
      <SectionHeading action={browseAction}>{t("codebook.heading")}</SectionHeading>
      <p className="codebook-description">
        {t("codebook.description")}
      </p>

      <div className="codebook-grid" id="codebook-grid">
        {/* Anchor for sidebar "Your tags" scroll — must be a real box (not display:contents) */}
        <div id="codebook-project" />
        {/* "<project> tags" section header — reuses the framework-section-header
            layout for the symmetric title-left / action-right slot. The action
            is the Codebook lab experiment (opens in a new window/popout). */}
        <div className="framework-section-header">
          <div>
            <div className="framework-section-title">
              {projectName
                ? t("codebook.projectTagsHeading", { project: projectName })
                : t("codebook.yourTags")}
            </div>
          </div>
          <div className="framework-section-actions">
            {/* Codebook Lab needs a server (and would open a dead file:// window
                offline) — hide it in an exported report. */}
            {!isExportMode() && (
              <button
                className="bn-btn bn-btn-secondary"
                onClick={() =>
                  window.open(
                    "/codebook-lab",
                    "_blank",
                    "width=1200,height=920,resizable=yes",
                  )
                }
                data-testid="bn-codebook-lab-btn"
              >
                {t("codebook.codebookLab")}
              </button>
            )}
          </div>
        </div>
        {researcherGroups.map((group) => (
          <CodebookGroupColumn
            key={group.id}
            group={group}
            allTagNames={data.all_tag_names}
            {...authoring.groupProps}
          />
        ))}

        {/* New group placeholder — creating a group needs a server, so the
            component hides itself offline. */}
        <NewGroupPlaceholder
          onCreateGroup={authoring.onCreateGroup}
          onDropNewGroup={authoring.onDropNewGroup}
        />

        {/* Per-framework sections — each imported framework gets its own header + remove button */}
        {Array.from(frameworkById.entries()).map(([fid, fwGroups]) => {
          const tmpl = templates?.find((t) => t.id === fid);
          const title = tmpl?.title ?? t("codebook.codebookFramework");
          const author = tmpl?.author ?? "";
          const label = author ? `${author} — ${title}` : title;
          const acStatus = autoCodeStatus[fid];
          const acDisabled = acStatus?.status === "running" || acStatus?.status === "completed";
          const proposedCount = acStatus?.proposed_count ?? 0;
          // Sentiment is auto-applied during the analysis pipeline — every quote
          // already carries its sentiment tag by the time the Codebook page
          // loads, so AutoCode can never produce proposals here. Hide the button
          // rather than show one that always returns "0 of 0 proposals"
          // (the fake-success-feedback class from the 7 May quality reset).
          const isSentimentFramework = fid === "sentiment";
          const isDisabled = disabledFrameworks.has(fid);
          // When switched off, the groups fold away; a one-line summary takes
          // their place so the researcher still sees what they've tucked away.
          // Distinct across the framework, not the sum of its groups — a quote
          // tagged in two groups is one quote. Register B6.
          const summary = summariseFramework(
            fwGroups,
            data.framework_quote_totals?.[fid],
          );
          return (
            <Fragment key={fid}>
              <div className="framework-section-header" id={`codebook-fw-${fid}`}>
                <div>
                  <div className="framework-section-title">{title}</div>
                  {author && <div className="framework-section-author">{author}</div>}
                  {isDisabled && (
                    <div className="framework-section-summary">
                      {t("codebook.foldedSummary", {
                        count: summary.tagCount,
                        coded: summary.codedQuotes,
                      })}
                    </div>
                  )}
                </div>
                <div className="framework-section-actions">
                  {!isSentimentFramework && (acStatus?.status === "completed" && proposedCount > 0 ? (
                    <button
                      className="autocode-btn autocode-btn-report"
                      onClick={() => handleOpenReport(fid, title)}
                      data-testid={`bn-autocode-report-btn-${fid}`}
                    >
                      {t("codebook.viewReport")}
                      <span
                        className="proposed-count"
                        data-testid={`bn-autocode-count-${fid}`}
                      >
                        {proposedCount}
                      </span>
                    </button>
                  ) : (
                    <button
                      className="autocode-btn"
                      disabled={acDisabled}
                      onClick={() => handleStartAutoCode(fid, title)}
                      data-testid={`bn-autocode-btn-${fid}`}
                    >
                      {t("codebook.autoCodeQuotes")}
                    </button>
                  ))}
                  <button
                    className="bn-btn framework-remove-btn"
                    onClick={() => handleAskRemoveFramework(fid, label)}
                  >
                    {t("codebook.removeFromCodebook")}
                  </button>
                  <button
                    type="button"
                    role="switch"
                    aria-checked={!isDisabled}
                    aria-label={label}
                    className={`framework-toggle${isDisabled ? " off" : ""}`}
                    onClick={() => toggleFramework(fid, title)}
                    data-testid={`bn-framework-toggle-${fid}`}
                  />
                </div>
              </div>
              {!isDisabled && fwGroups.map((group) => (
                <CodebookGroupColumn
                  key={group.id}
                  group={group}
                  allTagNames={data.all_tag_names}
                  {...authoring.groupProps}
                />
              ))}
            </Fragment>
          );
        })}
      </div>

      {/* Merge confirmation — centred overlay */}
      <MergeConfirm
        pending={authoring.pendingMerge}
        onConfirm={authoring.onConfirmMerge}
        onCancel={authoring.onCancelMerge}
      />

      {/* Remove framework confirmation */}
      {removeConfirm && (
        <div className="merge-overlay">
          <ConfirmDialog
            title={t("codebook.hideTitle", { label: removeConfirm.label })}
            body={
              <span>
                {removeConfirm.impact
                  ? (removeConfirm.impact.quote_count > 0
                    ? t("codebook.tagsRemovedFromQuotes", { count: removeConfirm.impact.quote_count })
                    : t("codebook.noQuotesTagged"))
                  : t("codebook.loadingImpact")}
                {" "}
                {/* `codebook.autoCodePreserved` USED TO BE THE has_autocode
                    arm, and it said "AutoCode results are preserved — reinstall
                    any time". `remove_framework` deletes the AutoCode job and
                    every proposal under it; its own docstring says "Nothing is
                    preserved." So a destructive confirmation carried a false
                    reassurance, in 21 locales, on the one screen a researcher
                    reads before losing reviewed work.

                    Both arms now take `restoreAnytime`, which is true of both:
                    reinstalling is possible, it just starts empty. That is
                    incomplete rather than wrong, and it needs no new
                    translation — the v2 sheet is where the full cost is
                    measured, and v2 replaces this lens. `autoCodePreserved` is
                    left in the locale files as an orphan rather than swept from
                    21 of them by regex; see codebook-defects.md. */}
                {t("codebook.restoreAnytime")}
              </span>
            }
            confirmLabel={t("codebook.hide")}
            variant="danger"
            onConfirm={handleConfirmRemoveFramework}
            onCancel={() => setRemoveConfirm(null)}
          />
        </div>
      )}

      {/* AutoCode threshold review modal */}
      <ThresholdReviewModal
        open={reportModal !== null}
        frameworkId={reportModal?.frameworkId ?? ""}
        frameworkTitle={reportModal?.frameworkTitle ?? ""}
        onClose={() => setReportModal(null)}
        onApply={handleReportApply}
      />

      {/* Browse codebooks modal — picker and preview views.
         Portal to document.body so position:fixed escapes any ancestor
         stacking context (tab panels, dev overlay, etc.). */}
      {createPortal(
        // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
        <div
          className={`codebook-modal-overlay${modalView !== "closed" ? " visible" : ""}`}
          onClick={handleCloseModal}
          aria-hidden={modalView === "closed"}
        >
          {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
          <div className="codebook-modal" onClick={(e) => e.stopPropagation()}>
            {modalView === "picker" && (
              <>
                <div className="codebook-modal-header">
                  <div>
                    <div className="codebook-modal-title">{t("codebook.browseTitle")}</div>
                    <div className="codebook-modal-subtitle">{t("codebook.browseSubtitle")}</div>
                  </div>
                  <button
                    className="codebook-modal-close"
                    onClick={handleCloseModal}
                    aria-label={t("buttons.close")}
                  >
                    &times;
                  </button>
                </div>
                <div className="codebook-modal-body">
                  {!templates ? (
                    <p>{t("labels.loading")}</p>
                  ) : (
                    <>
                      <div className="picker-section-header">
                        <span className="picker-section-title">{t("codebook.frameworksHeader")}</span>
                      </div>
                      <div className="picker-row">
                        {templates.map((tmpl) => {
                          const isClickable = tmpl.enabled && !tmpl.imported;
                          const cardClass = [
                            "picker-card",
                            tmpl.imported ? "imported" : null,
                            !tmpl.enabled ? "disabled" : null,
                          ].filter(Boolean).join(" ");
                          return (
                            // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
                            <div
                              key={tmpl.id}
                              className={cardClass}
                              onClick={() => isClickable && handleSelectTemplate(tmpl)}
                            >
                              <div className="picker-card-title">{tmpl.title}</div>
                              {tmpl.author && (
                                <div className="picker-card-author">{tmpl.author}</div>
                              )}
                              <div className="picker-card-desc">{tmpl.description}</div>
                              <div className="picker-card-tags">
                                {tmpl.groups.slice(0, 3).flatMap((g) =>
                                  g.tags.slice(0, 2).map((tag) => (
                                    <span
                                      key={`${g.name}-${tag.name}`}
                                      className="badge readonly"
                                      style={{ backgroundColor: getTagBg(tag.colour_set, tag.colour_index) }}
                                    >
                                      {tag.name}
                                    </span>
                                  )),
                                )}
                              </div>
                              {!tmpl.enabled && (
                                <div className="picker-card-coming">{t("codebook.comingSoon")}</div>
                              )}

                              {/* Per-tile Install ↔ Uninstall toggle. Coming-soon
                                  (disabled) codebooks get no action. stopPropagation
                                  keeps the card-body preview click from also firing. */}
                              {tmpl.enabled && (
                                <div className="picker-card-actions">
                                  {tmpl.imported ? (
                                    <button
                                      type="button"
                                      className="bn-btn bn-btn-secondary picker-card-toggle picker-card-toggle-uninstall"
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleUninstallFromLibrary(tmpl);
                                      }}
                                      data-testid={`bn-library-uninstall-${tmpl.id}`}
                                    >
                                      {t("codebook.removeFromCodebook")}
                                    </button>
                                  ) : (
                                    <button
                                      type="button"
                                      className="bn-btn bn-btn-primary picker-card-toggle"
                                      // Serialise installs: disable every Install
                                      // button while one is in flight, so an
                                      // enabled-looking button can't eat a click.
                                      disabled={pendingTemplateId !== null}
                                      onClick={(e) => {
                                        e.stopPropagation();
                                        handleInstallFromLibrary(tmpl);
                                      }}
                                      data-testid={`bn-library-install-${tmpl.id}`}
                                    >
                                      {pendingTemplateId === tmpl.id
                                        ? t("codebook.importingCodebook")
                                        : t("codebook.importCodebook")}
                                    </button>
                                  )}
                                </div>
                              )}
                            </div>
                          );
                        })}
                      </div>

                      {/* "Your codebooks" is not built (design-codebook-library.md
                          Q2 — per-project; a shared personal shelf deferred). It
                          shipped as a header plus a "+ Create new codebook" tile
                          whose only handler closed the modal, so the section's one
                          affordance silently did nothing. Removed 22 Aug 2026:
                          an absent control is honest, a no-op one teaches the
                          researcher the Library is unreliable. Restore header and
                          tile together, wired to a real create flow. */}
                    </>
                  )}
                </div>
              </>
            )}

            {modalView === "preview" && selectedTemplate && (
              <>
                <div className="codebook-modal-header">
                  <div style={{ flex: 1 }}>
                    <div className="codebook-modal-title">{selectedTemplate.title}</div>
                    <div className="codebook-modal-subtitle">{selectedTemplate.author}</div>
                  </div>
                  <div style={{ textAlign: "right", flexShrink: 0 }}>
                    <button
                      className="bn-btn bn-btn-primary"
                      onClick={handleImportTemplate}
                      disabled={importing}
                    >
                      {importing
                        ? t("codebook.importingCodebook")
                        : t("codebook.importCodebook")}
                    </button>
                    <div className="preview-cta-help">
                      {t("codebook.importHelp")}
                    </div>
                  </div>
                  <button
                    className="codebook-modal-close"
                    onClick={handleCloseModal}
                    aria-label={t("buttons.close")}
                  >
                    &times;
                  </button>
                </div>
                <div className="codebook-modal-body">
                  <div className="preview-body">
                    <div className="preview-body-main">
                      <div className="preview-desc">{selectedTemplate.description}</div>
                      <div className="preview-section-label">{t("codebook.tagGroups")}</div>
                      <div className="preview-groups">
                        {selectedTemplate.groups.map((g) => (
                          <div
                            key={g.name}
                            className="codebook-group"
                            style={{ backgroundColor: getGroupBg(g.colour_set) }}
                          >
                            <div className="group-header">
                              <div className="group-title-area">
                                <div className="group-title">{g.name}</div>
                                <div className="group-subtitle">{g.subtitle}</div>
                              </div>
                            </div>
                            <div className="tag-list">
                              {g.tags.map((tag) => (
                                <div key={tag.name} className="tag-row">
                                  <div className="tag-name-area">
                                    <span
                                      className="badge readonly"
                                      style={{ backgroundColor: getTagBg(tag.colour_set, tag.colour_index) }}
                                    >
                                      {tag.name}
                                    </span>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                    {selectedTemplate.author_bio && (
                      <div className="preview-body-sidebar">
                        <div className="preview-author">
                          <div className="preview-author-name">{selectedTemplate.author}</div>
                          <div className="preview-author-bio">{selectedTemplate.author_bio}</div>
                          {safeAuthorLinks.length > 0 && (
                            <div className="preview-author-links">
                              {/* href comes from codebook YAML, which the
                                  maintainer curates today and the community may
                                  submit tomorrow (the public-library item).
                                  html-escaping does not neutralise
                                  `javascript:`, so the scheme is allowlisted —
                                  see utils/safeUrl.ts. An unsafe link is
                                  dropped, not rendered inert: a link that does
                                  nothing is worse than no link. */}
                              {safeAuthorLinks.map((link) => (
                                <a key={link.href} href={link.href} target="_blank" rel="noopener noreferrer">
                                  {link.label} &#x2197;
                                </a>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>,
        document.body,
      )}
    </section>
  );
}
