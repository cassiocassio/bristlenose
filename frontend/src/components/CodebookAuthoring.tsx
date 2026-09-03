/**
 * The codebook's authoring apparatus — one implementation, two lenses.
 *
 * Add and delete a group; add, rename and delete a tag; drag a tag between
 * groups; drop a tag on another to merge. Extracted verbatim from
 * `islands/CodebookPanel.tsx` on 30 Aug 2026 so that `CodebookV2Page` renders
 * the same tree rather than a second one. The user's instruction was that v2
 * take the apparatus *directly* from the shipped implementation, and two
 * implementations of one behaviour drift from the day they ship.
 *
 * **This is a move, not a redesign.** Every class name, every confirmation, and
 * every absence of one is what the shipped lens already did — including the
 * details a test would not think to ask for:
 *
 * - Deleting a zero-count tag skips the confirmation. A tag nobody used is not
 *   a loss worth a dialog.
 * - The floor group (`is_default`) has no delete button; a framework's groups
 *   have none either. Read-only is one predicate here (`isReadOnly`), so both
 *   lenses inherit the same rule instead of each deciding.
 * - The badge *text* is the rename affordance — not a dialog, not a pencil.
 * - The delete confirmations are absolute-positioned inside the group card
 *   (`.codebook-group .confirm-dialog`), not modal overlays. Only the merge
 *   confirmation is centred, because it names two groups' worth of tags.
 *
 * The CSS lives in `bristlenose/theme/organisms/codebook-panel.css` and was not
 * touched by the extraction: if a class here changes, that file has to change
 * with it, and the point of the move is that neither does.
 *
 * The handler cluster that drives all of this is `hooks/useCodebookAuthoring`.
 */

import { useCallback, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "./Badge";
import { ConfirmDialog } from "./ConfirmDialog";
import { EditableText } from "./EditableText";
import { MicroBar } from "./MicroBar";
import { TagInput } from "./TagInput";
import { getBarColour, getGroupBg, getTagBg } from "../utils/colours";
import { isExportMode } from "../utils/exportData";
import type { CodebookGroupResponse, CodebookTagResponse } from "../utils/types";

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

export function TagRow({
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

/**
 * The handlers a group column needs, as one bundle.
 *
 * Named and exported rather than inlined so that both lenses spread the *same*
 * object: `useCodebookAuthoring` returns exactly this shape, which makes it
 * impossible for one lens to wire a handler the other forgot. Two call sites
 * each listing ten props is how the two implementations this extraction exists
 * to prevent would grow back one prop at a time.
 */
export interface CodebookGroupHandlers {
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

interface CodebookGroupColumnProps extends CodebookGroupHandlers {
  group: CodebookGroupResponse;
  allTagNames: string[];
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
export function GroupSubtitle({
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

export function CodebookGroupColumn({
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

  const handleRequestDeleteGroup = useCallback(() => {
    if (group.tags.length === 0) {
      // No tags to move — skip confirmation
      onDeleteGroup(group);
    } else {
      setShowDeleteConfirm(true);
    }
  }, [group, onDeleteGroup]);

  const classes = [
    "codebook-group",
    isDragOver ? "drag-over" : null,
  ].filter(Boolean).join(" ");

  const isDefault = group.is_default;
  const isFramework = group.framework_id != null;
  // An exported report is a read-only reference ("the taxonomy we coded
  // against") — no server to persist codebook edits, so gate every authoring
  // affordance (rename/delete/add-tag/drag) the same way built-in groups are.
  const isReadOnly = isDefault || isFramework || isExportMode();

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
            onClick={handleRequestDeleteGroup}
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
        <div
          className="tag-add-row"
          role="button"
          tabIndex={0}
          onClick={() => setIsAddingTag(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setIsAddingTag(true);
            }
          }}
        >
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

/**
 * The new-group card, which is also a drop target.
 *
 * Dropping a tag here creates the group *and* moves the tag in one gesture —
 * `onDropNewGroup` owns both calls, so the placeholder does not know it is
 * doing two things.
 *
 * The export-mode gate moved inside the component with the markup: creating a
 * group needs a server, and an exported report has none. Hidden rather than
 * disabled, which is the house pattern for export mode.
 */
export function NewGroupPlaceholder({
  onCreateGroup,
  onDropNewGroup,
}: {
  onCreateGroup: () => void;
  onDropNewGroup: (e: React.DragEvent) => void;
}) {
  const { t } = useTranslation();
  if (isExportMode()) return null;
  return (
    <div
      className="codebook-group new-group-placeholder"
      role="button"
      tabIndex={0}
      onClick={onCreateGroup}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onCreateGroup();
        }
      }}
      onDragOver={(e) => { e.preventDefault(); e.dataTransfer.dropEffect = "move"; }}
      onDrop={onDropNewGroup}
    >
      <span className="new-group-icon">+</span>
      <span className="new-group-label">{t("codebook.newGroup")}</span>
    </div>
  );
}

/**
 * The merge confirmation — the one dialog here that is *not* inline in a card.
 *
 * It names two tags that may sit in different groups, and it says what the act
 * costs ("all quotes tagged X will be retagged Y. This cannot be undone."), so
 * it is centred over the lens rather than covering one card. Renders nothing
 * when there is no pending merge, so both lenses carry the same single line.
 */
export function MergeConfirm({
  pending,
  onConfirm,
  onCancel,
}: {
  pending: { source: CodebookTagResponse; target: CodebookTagResponse } | null;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { t } = useTranslation();
  if (!pending) return null;
  return (
    <div className="merge-overlay">
      <ConfirmDialog
        title={t("codebook.mergeTitle", { source: pending.source.name, target: pending.target.name })}
        body={
          <span
            dangerouslySetInnerHTML={{
              __html: t("codebook.mergeBody", { source: pending.source.name, target: pending.target.name }),
            }}
          />
        }
        confirmLabel={t("codebook.merge")}
        variant="primary"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />
    </div>
  );
}

/**
 * The refused-rename notice — Finder's model: the name is already taken, OK,
 * and the title has already snapped back (the write never happened, so the
 * display never left the stored name). An acknowledgement rather than a
 * choice, hence one button. Renders nothing when there is no clash, so the
 * lens carries a single line, same as `MergeConfirm`.
 */
export function NameClashDialog({
  name,
  onDismiss,
}: {
  name: string | null;
  onDismiss: () => void;
}) {
  const { t } = useTranslation();
  if (name === null) return null;
  return (
    <div className="merge-overlay">
      <ConfirmDialog
        title={t("codebook.nameTaken", { name })}
        confirmLabel={t("buttons.ok")}
        variant="primary"
        hideCancel
        onConfirm={onDismiss}
        onCancel={onDismiss}
      />
    </div>
  );
}
