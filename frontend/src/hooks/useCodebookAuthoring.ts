/**
 * The codebook's authoring handlers — one cluster, two lenses.
 *
 * Lifted verbatim from `islands/CodebookPanel.tsx` on 30 Aug 2026 alongside the
 * components in `components/CodebookAuthoring.tsx`. Seven API calls and the drag
 * bookkeeping, in one place, so that the two lenses then live were the *same*
 * implementation rather than two that agree today. `CodebookPanel` was deleted
 * in 0.29.0, so `CodebookV2` is now the sole caller — the extraction outlived
 * its original reason and is kept because the cluster is worth naming.
 *
 * The contract is deliberately thin: the caller owns the data and says how to
 * re-read it (`onChanged`), and passes the groups it already has so a new group
 * can pick a colour set nothing else is using. Nothing here holds codebook
 * state of its own except the pending merge, which is a question awaiting an
 * answer rather than data.
 *
 * A failure says "Couldn't save" and re-reads (20 Oct 2026, R6). It used to
 * `console.error` and stop, as the shipped lens did when this was extracted
 * (`docs/design-codebook-v2-plan.md`), which left a refused rename looking
 * like nothing had happened.
 */

import { useCallback, useMemo, useRef, useState } from "react";
import i18n from "../i18n";
import {
  createCodebookGroup,
  createCodebookTag,
  deleteCodebookGroup,
  deleteCodebookTag,
  mergeCodebookTags,
  toastSaveFailed,
  updateCodebookGroup,
  updateCodebookTag,
} from "../utils/api";
import type { ApiError } from "../utils/api";
import type { CodebookGroupHandlers } from "../components/CodebookAuthoring";
import type { CodebookGroupResponse, CodebookTagResponse } from "../utils/types";

/** Colour sets a new group may claim, in the order they are offered. */
const COLOUR_SET_ORDER = ["ux", "emo", "task", "trust", "opp"];

export interface PendingMerge {
  source: CodebookTagResponse;
  target: CodebookTagResponse;
}

export interface CodebookAuthoring {
  /** Spread straight onto `CodebookGroupColumn`. */
  groupProps: CodebookGroupHandlers;
  /** The new-group card's two handlers. */
  onCreateGroup: () => void;
  onDropNewGroup: (e: React.DragEvent) => void;
  /** The pending merge, and its answer. Feed to `MergeConfirm`. */
  pendingMerge: PendingMerge | null;
  onConfirmMerge: () => void;
  onCancelMerge: () => void;
  /** A rename (group or tag) or a new tag refused because the name is taken. Feed to `NameClashDialog`. */
  nameClash: string | null;
  onDismissNameClash: () => void;
}

interface Options {
  /**
   * Every group in the codebook, framework ones included — not just the ones on
   * screen. A new group's colour set is chosen by what is *unused*, and asking
   * only the visible groups would hand out a colour a framework already has.
   */
  groups: CodebookGroupResponse[] | undefined;
  /** Re-read the codebook. Called after every successful mutation. */
  onChanged: () => void;
}

export function useCodebookAuthoring({ groups, onChanged }: Options): CodebookAuthoring {
  const dragTagRef = useRef<{ tag: CodebookTagResponse; fromGroupId: number } | null>(null);
  const [pendingMerge, setPendingMerge] = useState<PendingMerge | null>(null);
  const [nameClash, setNameClash] = useState<string | null>(null);

  // An edit that did not save says why ("Couldn't save"; a name another tag
  // holds is the server's 409), then re-reads, so the screen shows what saved.
  // These went to the console only, and a refused rename looked like nothing.
  // Only when the server answered: with the connection down, a re-read would
  // fail the same way and put up an error of its own.
  const failed = useCallback(
    (err: unknown) => {
      console.error("Codebook edit failed:", err);
      toastSaveFailed(err);
      if (typeof (err as ApiError | null)?.status === "number") onChanged();
    },
    [onChanged],
  );

  // A tag name another tag holds is the server's plain 409 (any case, any group
  // in the project): said by name in the dialog a group rename uses, not as
  // "Couldn't save", then re-read so the title snaps back (RE#20, decision #20).
  // A 409 carrying a reason is a refusal of another kind, said by `failed`.
  const tagNameFailed = useCallback(
    (name: string) => (err: unknown) => {
      const { status, reason } = (err ?? {}) as ApiError;
      if (status !== 409 || reason) {
        failed(err);
        return;
      }
      setNameClash(name);
      onChanged();
    },
    [failed, onChanged],
  );

  const nextColourSet = useCallback(() => {
    const usedSets = new Set(groups?.map((g) => g.colour_set) ?? []);
    return COLOUR_SET_ORDER.find((s) => !usedSets.has(s)) ?? "ux";
  }, [groups]);

  /**
   * The first name no other group holds: the base itself, then "base 2",
   * "base 3", … Checked against every group, frameworks included — and against
   * the *current* names, so once the first "New group" is renamed the plain
   * name is free again.
   */
  const nextGroupName = useCallback(() => {
    const taken = new Set(groups?.map((g) => g.name) ?? []);
    const base = i18n.t("codebook.newGroup");
    if (!taken.has(base)) return base;
    let n = 2;
    while (taken.has(`${base} ${n}`)) n += 1;
    return `${base} ${n}`;
  }, [groups]);

  // --- Group mutations ---

  const onUpdateGroup = useCallback(
    (groupId: number, fields: { name?: string; subtitle?: string }) => {
      // A rename to a name another group already holds is refused, Finder-style:
      // no write, a dialog naming the clash, and the title snaps back to what it
      // was (the display always renders the stored name). "Uncategorised" is a
      // real clash too — the server looks the floor group up *by that name*.
      if (
        fields.name !== undefined &&
        groups?.some((g) => g.id !== groupId && g.name === fields.name)
      ) {
        setNameClash(fields.name);
        return;
      }
      updateCodebookGroup(groupId, fields)
        .then(onChanged)
        .catch(failed);
    },
    [groups, onChanged, failed],
  );

  const onDeleteGroup = useCallback(
    (group: CodebookGroupResponse) => {
      deleteCodebookGroup(group.id)
        .then(onChanged)
        .catch(failed);
    },
    [onChanged, failed],
  );

  const onCreateGroup = useCallback(() => {
    createCodebookGroup(nextGroupName(), nextColourSet())
      .then(onChanged)
      .catch(failed);
  }, [nextGroupName, nextColourSet, onChanged, failed]);

  // --- Tag mutations ---

  const onCreateTag = useCallback(
    (name: string, groupId: number) => {
      createCodebookTag(name, groupId)
        .then(onChanged)
        .catch(tagNameFailed(name));
    },
    [onChanged, tagNameFailed],
  );

  const onDeleteTag = useCallback(
    (tag: CodebookTagResponse) => {
      deleteCodebookTag(tag.id)
        .then(onChanged)
        .catch(failed);
    },
    [onChanged, failed],
  );

  const onRenameTag = useCallback(
    (tag: CodebookTagResponse, newName: string) => {
      updateCodebookTag(tag.id, { name: newName })
        .then(onChanged)
        .catch(tagNameFailed(newName));
    },
    [onChanged, tagNameFailed],
  );

  // --- Drag and drop ---

  const onDragStart = useCallback((tag: CodebookTagResponse, fromGroupId: number) => {
    dragTagRef.current = { tag, fromGroupId };
  }, []);

  const onDragEnd = useCallback(() => {
    dragTagRef.current = null;
  }, []);

  const onDropTag = useCallback(
    (targetGroupId: number) => {
      const dragInfo = dragTagRef.current;
      if (!dragInfo) return;
      if (dragInfo.fromGroupId === targetGroupId) return;
      dragTagRef.current = null;
      updateCodebookTag(dragInfo.tag.id, { group_id: targetGroupId })
        .then(onChanged)
        .catch(failed);
    },
    [onChanged, failed],
  );

  const onMergeDrop = useCallback((targetTag: CodebookTagResponse) => {
    const dragInfo = dragTagRef.current;
    if (!dragInfo) return;
    if (dragInfo.tag.id === targetTag.id) return;
    dragTagRef.current = null;
    setPendingMerge({ source: dragInfo.tag, target: targetTag });
  }, []);

  const onConfirmMerge = useCallback(() => {
    if (!pendingMerge) return;
    mergeCodebookTags(pendingMerge.source.id, pendingMerge.target.id)
      .then(onChanged)
      .catch(failed);
    setPendingMerge(null);
  }, [pendingMerge, onChanged, failed]);

  const onCancelMerge = useCallback(() => setPendingMerge(null), []);

  const onDismissNameClash = useCallback(() => setNameClash(null), []);

  const onDropNewGroup = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      const dragInfo = dragTagRef.current;
      if (!dragInfo) return;
      dragTagRef.current = null;
      createCodebookGroup(nextGroupName(), nextColourSet())
        .then((newGroup) => updateCodebookTag(dragInfo.tag.id, { group_id: newGroup.id }))
        .then(onChanged)
        .catch(failed);
    },
    [nextGroupName, nextColourSet, onChanged, failed],
  );

  // Memoised so the bundle has the same reference stability the ten separate
  // callbacks had before they were bundled — a spread of a fresh object every
  // render would quietly defeat any future memo on the column.
  const groupProps = useMemo(
    (): CodebookGroupHandlers => ({
      onUpdateGroup,
      onDeleteGroup,
      onCreateTag,
      onDeleteTag,
      onRenameTag,
      onDragStart,
      onDragEnd,
      onDropTag,
      onMergeDrop,
    }),
    [
      onUpdateGroup,
      onDeleteGroup,
      onCreateTag,
      onDeleteTag,
      onRenameTag,
      onDragStart,
      onDragEnd,
      onDropTag,
      onMergeDrop,
    ],
  );

  return {
    groupProps,
    onCreateGroup,
    onDropNewGroup,
    pendingMerge,
    onConfirmMerge,
    onCancelMerge,
    nameClash,
    onDismissNameClash,
  };
}
