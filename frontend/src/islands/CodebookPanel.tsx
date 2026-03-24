import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { useTranslation } from "react-i18next";
import {
  Badge,
  ConfirmDialog,
  EditableText,
  MicroBar,
  TagInput,
  ThresholdReviewModal,
} from "../components";
import { addJob } from "../contexts/ActivityStore";
import {
  createCodebookGroup,
  createCodebookTag,
  deleteCodebookGroup,
  deleteCodebookTag,
  getAutoCodeStatus,
  getCodebook,
  getCodebookTemplates,
  getRemoveFrameworkImpact,
  importCodebookTemplate,
  mergeCodebookTags,
  removeCodebookFramework,
  startAutoCode,
  updateCodebookGroup,
  updateCodebookTag,
} from "../utils/api";
import type {
  AutoCodeJobStatus,
  CodebookGroupResponse,
  CodebookResponse,
  CodebookTagResponse,
  RemoveFrameworkInfo,
  TemplateOut,
} from "../utils/types";

// ---------------------------------------------------------------------------
// Colour helpers — shared module (see utils/colours.ts)
// ---------------------------------------------------------------------------

import { getGroupBg, getBarColour, getTagBg } from "../utils/colours";

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

interface TagRowProps {
  tag: CodebookTagResponse;
  maxCount: number;
  colourSet: string;
  groupId: number;
  onRequestDelete: (tag: CodebookTagResponse) => void;
  onRenameTag: (tag: CodebookTagResponse, newName: string) => void;
  onDragStart: (tag: CodebookTagResponse, groupId: number) => void;
  onDragEnd: () => void;
  onMergeDrop: (targetTag: CodebookTagResponse) => void;
}

function TagRow({
  tag,
  maxCount,
  colourSet,
  groupId,
  onRequestDelete,
  onRenameTag,
  onDragStart,
  onDragEnd,
  onMergeDrop,
}: TagRowProps) {
  const [isMergeTarget, setIsMergeTarget] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const dragOverCount = useRef(0);

  const handleDragStart = useCallback(
    (e: React.DragEvent) => {
      e.dataTransfer.effectAllowed = "move";
      e.dataTransfer.setData("text/plain", String(tag.id));
      // Create a custom drag ghost from the badge only (not the whole row)
      const badge = (e.currentTarget as HTMLElement).querySelector(".badge");
      if (badge) {
        const ghost = badge.cloneNode(true) as HTMLElement;
        ghost.classList.add("drag-ghost");
        ghost.style.position = "fixed";
        ghost.style.top = "-1000px";
        document.body.appendChild(ghost);
        e.dataTransfer.setDragImage(ghost, ghost.offsetWidth / 2, ghost.offsetHeight / 2);
        // Clean up the clone after a frame
        requestAnimationFrame(() => document.body.removeChild(ghost));
      }
      onDragStart(tag, groupId);
    },
    [tag, groupId, onDragStart],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragOverCount.current++;
    setIsMergeTarget(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    dragOverCount.current--;
    if (dragOverCount.current <= 0) {
      dragOverCount.current = 0;
      setIsMergeTarget(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      dragOverCount.current = 0;
      setIsMergeTarget(false);
      onMergeDrop(tag);
    },
    [tag, onMergeDrop],
  );

  const hasTentative = (tag.tentative_count ?? 0) > 0;
  const barColour = getBarColour(colourSet);

  const classes = [
    "tag-row",
    isMergeTarget ? "merge-target" : null,
  ].filter(Boolean).join(" ");

  return (
    <div
      className={classes}
      draggable={!isEditing}
      onDragStart={handleDragStart}
      onDragEnd={onDragEnd}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="tag-name-area">
        {isEditing ? (
          <EditableText
            as="span"
            value={tag.name}
            isEditing={true}
            trigger="external"
            className="badge tag-edit-inline"
            onCommit={(newName) => {
              setIsEditing(false);
              if (newName && newName !== tag.name) onRenameTag(tag, newName);
            }}
            onCancel={() => setIsEditing(false)}
          />
        ) : (
          <Badge
            text={tag.name}
            variant="deletable"
            colour={getTagBg(colourSet, tag.colour_index)}
            onClick={() => setIsEditing(true)}
            onDelete={() => onRequestDelete(tag)}
          />
        )}
      </div>
      <div className="tag-bar-area">
        {hasTentative ? (
          <MicroBar
            value={maxCount > 0 ? tag.count / maxCount : 0}
            tentativeValue={maxCount > 0 ? (tag.tentative_count ?? 0) / maxCount : 0}
            colour={barColour}
            title={`${tag.tentative_count ?? 0} tentative + ${tag.count} accepted`}
          />
        ) : tag.count > 0 ? (
          <MicroBar value={maxCount > 0 ? tag.count / maxCount : 0} colour={barColour} />
        ) : null}
        <span className="tag-count">{tag.count}</span>
      </div>
    </div>
  );
}

interface CodebookGroupColumnProps {
  group: CodebookGroupResponse;
  allTagNames: string[];
  onUpdateGroup: (groupId: number, fields: { name?: string; subtitle?: string }) => void;
  onDeleteGroup: (group: CodebookGroupResponse) => void;
  onCreateTag: (name: string, groupId: number) => void;
  onDeleteTag: (tag: CodebookTagResponse) => void;
  onRenameTag: (tag: CodebookTagResponse, newName: string) => void;
  onDragStart: (tag: CodebookTagResponse, groupId: number) => void;
  onDragEnd: () => void;
  onDropTag: (groupId: number) => void;
  onMergeDrop: (targetTag: CodebookTagResponse) => void;
}

// Placeholder key — resolved at render time via t().

/**
 * Group subtitle with placeholder support.
 *
 * When the subtitle is empty, shows italic placeholder text.
 * On click-to-edit, immediately switches to normal text style
 * (removes placeholder class) and shows an empty field instead
 * of the placeholder hint. Uses external editing control so
 * we can track the editing state and adjust styling/value.
 */
function GroupSubtitle({
  subtitle,
  onCommit,
}: {
  subtitle: string;
  onCommit: (text: string) => void;
}) {
  const { t } = useTranslation();
  const isEmpty = !subtitle;
  const [isEditing, setIsEditing] = useState(false);

  // When empty and not editing: show placeholder text with placeholder style.
  // When editing: show the actual subtitle (empty string if none) with normal style.
  const displayValue = isEmpty && !isEditing ? t("codebook.addSubtitle") : subtitle;
  const className = `group-subtitle${isEmpty && !isEditing ? " placeholder" : ""}`;

  return (
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
    <div onClick={() => { if (!isEditing) setIsEditing(true); }}>
      <EditableText
        as="p"
        value={displayValue}
        isEditing={isEditing}
        trigger="external"
        className={className}
        onCommit={(text) => {
          setIsEditing(false);
          onCommit(text);
        }}
        onCancel={() => setIsEditing(false)}
      />
    </div>
  );
}

function CodebookGroupColumn({
  group,
  allTagNames,
  onUpdateGroup,
  onDeleteGroup,
  onCreateTag,
  onDeleteTag,
  onRenameTag,
  onDragStart,
  onDragEnd,
  onDropTag,
  onMergeDrop,
}: CodebookGroupColumnProps) {
  const { t } = useTranslation();
  const te = useTranslation("enums").t;
  const [isDragOver, setIsDragOver] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [confirmingTag, setConfirmingTag] = useState<CodebookTagResponse | null>(null);
  const [isAddingTag, setIsAddingTag] = useState(false);
  const tagInputKey = useRef(0);
  const dragOverCount = useRef(0);

  // Translate built-in group labels (sentiment + uncategorised)
  const isSentiment = group.colour_set === "sentiment";
  const isUncategorised = group.name === "Uncategorised";
  const displayGroupName = isSentiment ? t("analysis.sentiment")
    : isUncategorised ? t("codebook.uncategorised")
    : group.name;
  const displayGroupSubtitle = isSentiment ? t("analysis.sentimentSubtitle")
    : isUncategorised ? t("codebook.uncategorisedSubtitle")
    : group.subtitle;

  const maxCount = Math.max(1, ...group.tags.map((tg) => tg.count + (tg.tentative_count ?? 0)));

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
  }, []);

  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    dragOverCount.current++;
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    dragOverCount.current--;
    if (dragOverCount.current <= 0) {
      dragOverCount.current = 0;
      setIsDragOver(false);
    }
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      dragOverCount.current = 0;
      setIsDragOver(false);
      onDropTag(group.id);
    },
    [group.id, onDropTag],
  );

  const handleTagCommit = useCallback(
    (name: string) => {
      setIsAddingTag(false);
      if (name.trim()) onCreateTag(name.trim(), group.id);
    },
    [group.id, onCreateTag],
  );

  const handleTagCommitAndReopen = useCallback(
    (name: string) => {
      if (name.trim()) onCreateTag(name.trim(), group.id);
      // Increment key to force TagInput remount (fresh empty input)
      tagInputKey.current++;
      setIsAddingTag(true);
    },
    [group.id, onCreateTag],
  );

  const handleRequestDeleteTag = useCallback((tag: CodebookTagResponse) => {
    if (tag.count === 0) {
      // No quotes affected — skip confirmation
      onDeleteTag(tag);
    } else {
      setConfirmingTag(tag);
    }
  }, [onDeleteTag]);

  const classes = [
    "codebook-group",
    isDragOver ? "drag-over" : null,
  ].filter(Boolean).join(" ");

  const isDefault = group.is_default;
  const isFramework = group.framework_id != null;
  const isReadOnly = isDefault || isFramework;

  return (
    <div
      className={classes}
      style={{ backgroundColor: getGroupBg(group.colour_set) }}
      onDragOver={handleDragOver}
      onDragEnter={handleDragEnter}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <div className="group-header">
        <div className="group-title-area">
          <div className="group-title">
            {isReadOnly || isSentiment ? (
              <span className="group-title-text">{displayGroupName}</span>
            ) : (
              <EditableText
                as="span"
                value={group.name}
                trigger="click"
                className="group-title-text"
                onCommit={(text) => onUpdateGroup(group.id, { name: text })}
                onCancel={() => {}}
              />
            )}
          </div>
          {isReadOnly || isSentiment ? (
            <p className="group-subtitle">{displayGroupSubtitle}</p>
          ) : (
            <GroupSubtitle
              subtitle={group.subtitle}
              onCommit={(text) => onUpdateGroup(group.id, { subtitle: text })}
            />
          )}
        </div>
        {!isReadOnly && (
          <button
            className="group-close"
            onClick={() => setShowDeleteConfirm(true)}
            aria-label={t("codebook.deleteGroupAriaLabel", { name: group.name })}
          >
            &times;
          </button>
        )}
      </div>

      <div className="tag-list">
        {group.tags.map((tag) => {
          const tagDisplayName = isSentiment
            ? te(`sentiment.${tag.name}`, { defaultValue: tag.name })
            : tag.name;
          return isFramework ? (
            <div key={tag.id} className="tag-row">
              <div className="tag-name-area">
                <Badge
                  text={tagDisplayName}
                  variant="readonly"
                  colour={getTagBg(group.colour_set, tag.colour_index)}
                />
              </div>
              <div className="tag-bar-area">
                {(tag.tentative_count ?? 0) > 0 ? (
                  <MicroBar
                    value={maxCount > 0 ? tag.count / maxCount : 0}
                    tentativeValue={maxCount > 0 ? (tag.tentative_count ?? 0) / maxCount : 0}
                    colour={getBarColour(group.colour_set)}
                    title={`${tag.tentative_count ?? 0} tentative + ${tag.count} accepted`}
                  />
                ) : tag.count > 0 ? (
                  <MicroBar value={maxCount > 0 ? tag.count / maxCount : 0} colour={getBarColour(group.colour_set)} />
                ) : null}
                <span className="tag-count">{tag.count}</span>
              </div>
            </div>
          ) : (
            <TagRow
              key={tag.id}
              tag={tag}
              maxCount={maxCount}
              colourSet={group.colour_set}
              groupId={group.id}
              onRequestDelete={handleRequestDeleteTag}
              onRenameTag={onRenameTag}
              onDragStart={onDragStart}
              onDragEnd={onDragEnd}
              onMergeDrop={onMergeDrop}
            />
          );
        })}
      </div>

      {group.total_quotes > 0 && (
        <div className="group-total-row">
          <span className="group-total-label">{t("codebook.total")}</span>
          <span className="group-total-count">{group.total_quotes}</span>
        </div>
      )}

      {!isFramework && (isAddingTag ? (
        <div className="tag-add-row">
          <TagInput
            key={tagInputKey.current}
            vocabulary={[]}
            exclude={allTagNames}
            onCommit={handleTagCommit}
            onCommitAndReopen={handleTagCommitAndReopen}
            onCancel={() => setIsAddingTag(false)}
          />
        </div>
      ) : (
        <div className="tag-add-row" onClick={() => setIsAddingTag(true)}>
          <span className="tag-add-badge">{t("codebook.addTag")}</span>
        </div>
      ))}

      {/* Tag-delete confirmation — rendered at group level for correct positioning */}
      {confirmingTag && (
        <ConfirmDialog
          title={t("codebook.deleteTagTitle", { name: confirmingTag.name })}
          body={
            confirmingTag.count > 0
              ? <span>{t("codebook.tagOnQuotes", { count: confirmingTag.count })}</span>
              : undefined
          }
          confirmLabel={t("buttons.delete")}
          variant="danger"
          accentColour={getBarColour(group.colour_set)}
          onConfirm={() => {
            const tag = confirmingTag;
            setConfirmingTag(null);
            onDeleteTag(tag);
          }}
          onCancel={() => setConfirmingTag(null)}
        />
      )}

      {/* Group-delete confirmation */}
      {showDeleteConfirm && !isReadOnly && (
        <ConfirmDialog
          title={t("codebook.deleteGroupTitle", { name: group.name })}
          body={
            group.tags.length > 0
              ? <span>{t("codebook.tagsWillMove", { count: group.tags.length })}</span>
              : undefined
          }
          confirmLabel={t("codebook.deleteGroup")}
          variant="danger"
          accentColour={getBarColour(group.colour_set)}
          onConfirm={() => {
            setShowDeleteConfirm(false);
            onDeleteGroup(group);
          }}
          onCancel={() => setShowDeleteConfirm(false)}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main island
// ---------------------------------------------------------------------------

interface CodebookPanelProps {
  projectId: string;
}

export function CodebookPanel({ projectId }: CodebookPanelProps) {
  const { t } = useTranslation();
  const [data, setData] = useState<CodebookResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const dragTagRef = useRef<{ tag: CodebookTagResponse; fromGroupId: number } | null>(null);
  const [mergeConfirm, setMergeConfirm] = useState<{
    source: CodebookTagResponse;
    target: CodebookTagResponse;
  } | null>(null);
  const [modalView, setModalView] = useState<"closed" | "picker" | "preview">("closed");
  const [templates, setTemplates] = useState<TemplateOut[] | null>(null);
  const [selectedTemplate, setSelectedTemplate] = useState<TemplateOut | null>(null);
  const [importing, setImporting] = useState(false);
  const [removeConfirm, setRemoveConfirm] = useState<{
    frameworkId: string;
    label: string;
    impact: RemoveFrameworkInfo | null;
  } | null>(null);

  // --- AutoCode state ---
  const [autoCodeStatus, setAutoCodeStatus] = useState<Record<string, AutoCodeJobStatus | null>>({});
  const [reportModal, setReportModal] = useState<{ frameworkId: string; frameworkTitle: string } | null>(null);

  // Fetch codebook data
  const fetchData = useCallback(() => {
    getCodebook()
      .then(setData)
      .catch((err) => setError(String(err)));
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData, projectId]);

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
            addJob(`autocode:${fid}`, { frameworkId: fid, frameworkTitle: title });
          }
        })
        .catch(() => {
          // 404 = no job yet, button should be enabled.
          setAutoCodeStatus((prev) => ({ ...prev, [fid]: null }));
        });
    }
  }, [data, templates]);

  // --- Group mutations ---

  const handleUpdateGroup = useCallback(
    (groupId: number, fields: { name?: string; subtitle?: string }) => {
      updateCodebookGroup(groupId, fields)
        .then(fetchData)
        .catch((err) => console.error("Update group failed:", err));
    },
    [fetchData],
  );

  const handleDeleteGroup = useCallback(
    (group: CodebookGroupResponse) => {
      deleteCodebookGroup(group.id)
        .then(fetchData)
        .catch((err) => console.error("Delete group failed:", err));
    },
    [fetchData],
  );

  const handleCreateGroup = useCallback(() => {
    const COLOUR_SET_ORDER = ["ux", "emo", "task", "trust", "opp"];
    const usedSets = new Set(data?.groups.map((g) => g.colour_set) ?? []);
    const nextSet = COLOUR_SET_ORDER.find((s) => !usedSets.has(s)) ?? "ux";
    createCodebookGroup("New group", nextSet)
      .then(fetchData)
      .catch((err) => console.error("Create group failed:", err));
  }, [data, fetchData]);

  // --- Tag mutations ---

  const handleCreateTag = useCallback(
    (name: string, groupId: number) => {
      createCodebookTag(name, groupId)
        .then(fetchData)
        .catch((err) => console.error("Create tag failed:", err));
    },
    [fetchData],
  );

  const handleDeleteTag = useCallback(
    (tag: CodebookTagResponse) => {
      deleteCodebookTag(tag.id)
        .then(fetchData)
        .catch((err) => console.error("Delete tag failed:", err));
    },
    [fetchData],
  );

  const handleRenameTag = useCallback(
    (tag: CodebookTagResponse, newName: string) => {
      updateCodebookTag(tag.id, { name: newName })
        .then(fetchData)
        .catch((err) => console.error("Rename tag failed:", err));
    },
    [fetchData],
  );

  // --- Drag and drop ---

  const handleDragStart = useCallback(
    (tag: CodebookTagResponse, fromGroupId: number) => {
      dragTagRef.current = { tag, fromGroupId };
    },
    [],
  );

  const handleDragEnd = useCallback(() => {
    dragTagRef.current = null;
  }, []);

  const handleDropTag = useCallback(
    (targetGroupId: number) => {
      const dragInfo = dragTagRef.current;
      if (!dragInfo) return;
      if (dragInfo.fromGroupId === targetGroupId) return;
      dragTagRef.current = null;
      updateCodebookTag(dragInfo.tag.id, { group_id: targetGroupId })
        .then(fetchData)
        .catch((err) => console.error("Move tag failed:", err));
    },
    [fetchData],
  );

  const handleMergeDrop = useCallback(
    (targetTag: CodebookTagResponse) => {
      const dragInfo = dragTagRef.current;
      if (!dragInfo) return;
      if (dragInfo.tag.id === targetTag.id) return;
      dragTagRef.current = null;
      setMergeConfirm({ source: dragInfo.tag, target: targetTag });
    },
    [],
  );

  const handleMergeConfirm = useCallback(() => {
    if (!mergeConfirm) return;
    mergeCodebookTags(mergeConfirm.source.id, mergeConfirm.target.id)
      .then(fetchData)
      .catch((err) => console.error("Merge tags failed:", err));
    setMergeConfirm(null);
  }, [mergeConfirm, fetchData]);

  const handleDropNewGroup = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const dragInfo = dragTagRef.current;
      if (!dragInfo) return;
      dragTagRef.current = null;
      const COLOUR_SET_ORDER = ["ux", "emo", "task", "trust", "opp"];
      const usedSets = new Set(data?.groups.map((g) => g.colour_set) ?? []);
      const nextSet = COLOUR_SET_ORDER.find((s) => !usedSets.has(s)) ?? "ux";
      createCodebookGroup("New group", nextSet)
        .then((newGroup) => {
          return updateCodebookTag(dragInfo.tag.id, { group_id: newGroup.id });
        })
        .then(fetchData)
        .catch((err) => console.error("Create group from drag failed:", err));
    },
    [data, fetchData],
  );

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
          addJob(`autocode:${frameworkId}`, { frameworkId, frameworkTitle });
        })
        .catch((err) => console.error("Start AutoCode failed:", err));
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

  const handleConfirmRemoveFramework = useCallback(() => {
    if (!removeConfirm) return;
    removeCodebookFramework(removeConfirm.frameworkId)
      .then((codebook) => {
        setData(codebook);
        setRemoveConfirm(null);
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
    const handler = () => handleCreateGroup();
    window.addEventListener("bn:codebook-create-group", handler);
    return () => window.removeEventListener("bn:codebook-create-group", handler);
  }, [handleCreateGroup]);

  // Listen for menu-bar "create code" requests (dispatched by AppLayout).
  // Adds a new tag to the first researcher (non-framework) group.
  useEffect(() => {
    const handler = () => {
      if (!data) return;
      const researcherGroup = data.groups
        .filter((g) => g.framework_id == null)
        .sort((a, b) => (a.is_default === b.is_default ? a.order - b.order : a.is_default ? -1 : 1))[0];
      if (researcherGroup) {
        handleCreateTag("New code", researcherGroup.id);
      }
    };
    window.addEventListener("bn:codebook-create-code", handler);
    return () => window.removeEventListener("bn:codebook-create-code", handler);
  }, [data, handleCreateTag]);

  // --- Render ---

  if (error) {
    return (
      <>
        <h1>{t("codebook.heading")}</h1>
        <p className="codebook-description">{t("codebook.errorLoading", { error })}</p>
      </>
    );
  }

  if (!data) {
    return (
      <>
        <h1>{t("codebook.heading")}</h1>
        <p className="codebook-description">{t("labels.loading")}</p>
      </>
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

  return (
    <>
      <div className="codebook-header">
        <div style={{ flex: 1, minWidth: 0 }}>
          <h1>{t("codebook.heading")}</h1>
          <p className="codebook-description">
            {t("codebook.description")}
          </p>
        </div>
        <button className="bn-btn bn-btn-primary" onClick={handleOpenPicker} style={{ flexShrink: 0 }}>
          {t("codebook.browseCodebooks")}
        </button>
      </div>

      <div className="codebook-grid" id="codebook-grid">
        {/* Anchor for sidebar "Your tags" scroll — must be a real box (not display:contents) */}
        <div id="codebook-project" />
        {researcherGroups.map((group) => (
          <CodebookGroupColumn
            key={group.id}
            group={group}
            allTagNames={data.all_tag_names}
            onUpdateGroup={handleUpdateGroup}
            onDeleteGroup={handleDeleteGroup}
            onCreateTag={handleCreateTag}
            onDeleteTag={handleDeleteTag}
            onRenameTag={handleRenameTag}
            onDragStart={handleDragStart}
            onDragEnd={handleDragEnd}
            onDropTag={handleDropTag}
            onMergeDrop={handleMergeDrop}
          />
        ))}

        {/* New group placeholder */}
        <div
          className="codebook-group new-group-placeholder"
          onClick={handleCreateGroup}
          onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }}
          onDrop={handleDropNewGroup}
        >
          <span className="new-group-icon">+</span>
          <span className="new-group-label">{t("codebook.newGroup")}</span>
        </div>

        {/* Per-framework sections — each imported framework gets its own header + remove button */}
        {Array.from(frameworkById.entries()).map(([fid, fwGroups]) => {
          const tmpl = templates?.find((t) => t.id === fid);
          const title = tmpl?.title ?? t("codebook.codebookFramework");
          const author = tmpl?.author ?? "";
          const label = author ? `${author} — ${title}` : title;
          const acStatus = autoCodeStatus[fid];
          const acDisabled = acStatus?.status === "running" || acStatus?.status === "completed";
          const proposedCount = acStatus?.proposed_count ?? 0;
          return (
            <Fragment key={fid}>
              <div className="framework-section-header" id={`codebook-fw-${fid}`}>
                <div>
                  <div className="framework-section-title">{title}</div>
                  {author && <div className="framework-section-author">{author}</div>}
                </div>
                <div className="framework-section-actions">
                  {acStatus?.status === "completed" && proposedCount > 0 ? (
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
                  )}
                  <button
                    className="bn-btn framework-remove-btn"
                    onClick={() => handleAskRemoveFramework(fid, label)}
                  >
                    {t("codebook.removeFromCodebook")}
                  </button>
                </div>
              </div>
              {fwGroups.map((group) => (
                <CodebookGroupColumn
                  key={group.id}
                  group={group}
                  allTagNames={data.all_tag_names}
                  onUpdateGroup={handleUpdateGroup}
                  onDeleteGroup={handleDeleteGroup}
                  onCreateTag={handleCreateTag}
                  onDeleteTag={handleDeleteTag}
                  onRenameTag={handleRenameTag}
                  onDragStart={handleDragStart}
                  onDragEnd={handleDragEnd}
                  onDropTag={handleDropTag}
                  onMergeDrop={handleMergeDrop}
                />
              ))}
            </Fragment>
          );
        })}
      </div>

      {/* Merge confirmation — centred overlay */}
      {mergeConfirm && (
        <div className="merge-overlay">
          <ConfirmDialog
            title={t("codebook.mergeTitle", { source: mergeConfirm.source.name, target: mergeConfirm.target.name })}
            body={
              <span
                dangerouslySetInnerHTML={{
                  __html: t("codebook.mergeBody", { source: mergeConfirm.source.name, target: mergeConfirm.target.name }),
                }}
              />
            }
            confirmLabel={t("codebook.merge")}
            variant="primary"
            onConfirm={handleMergeConfirm}
            onCancel={() => setMergeConfirm(null)}
          />
        </div>
      )}

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
                {removeConfirm.impact?.has_autocode
                  ? t("codebook.autoCodePreserved")
                  : t("codebook.restoreAnytime")}
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
                    aria-label="Close"
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
                            tmpl.restorable && !tmpl.imported ? "restorable" : null,
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
                              {tmpl.restorable && !tmpl.imported && (
                                <div className="picker-card-restore">{t("codebook.previouslyImported")}</div>
                              )}
                            </div>
                          );
                        })}
                      </div>

                      <div className="picker-section-header">
                        <span className="picker-section-title">{t("codebook.yourCodebooksHeader")}</span>
                      </div>
                      <div className="picker-row">
                        <div className="picker-card picker-card-create" onClick={handleCloseModal}>
                          <span className="new-icon">+</span>
                          <span className="new-label">{t("codebook.createNew")}</span>
                        </div>
                      </div>
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
                        ? (selectedTemplate.restorable ? t("codebook.restoringCodebook") : t("codebook.importingCodebook"))
                        : (selectedTemplate.restorable ? t("codebook.restoreCodebook") : t("codebook.importCodebook"))}
                    </button>
                    <div className="preview-cta-help">
                      {selectedTemplate.restorable
                        ? t("codebook.restoreHelp")
                        : t("codebook.importHelp")}
                    </div>
                  </div>
                  <button
                    className="codebook-modal-close"
                    onClick={handleCloseModal}
                    aria-label="Close"
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
                          {selectedTemplate.author_links.length > 0 && (
                            <div className="preview-author-links">
                              {selectedTemplate.author_links.map((link) => (
                                <a key={link.url} href={link.url} target="_blank" rel="noopener noreferrer">
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
    </>
  );
}
