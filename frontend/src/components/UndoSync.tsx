/**
 * UndoSync — connects the report's undo stack to the keys and menus that
 * drive it. Side-effect only; mounted once by AppLayout.
 *
 * - **Mac app:** posts `undo-state` so Edit ▸ Undo / Redo are enabled and
 *   carry the action name ("Undo Rename Moderator"), and answers the menu's
 *   `undo` / `redo` actions. ⌘Z itself belongs to the menu — the web view
 *   hands it over (WebView.swift) — so no key handler runs here.
 * - **Browser:** ⌘Z / Ctrl+Z undoes, ⇧⌘Z / Ctrl+Shift+Z / Ctrl+Y redoes,
 *   whenever focus is not in a text field (a field keeps its own text undo).
 *
 * A new run replaces the data the stack's entries describe, so the stack is
 * cleared when one lands.
 */

import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { useLastRun } from "../contexts/LastRunStore";
import { clearUndo, getUndoState, redo, undo, useUndoState } from "../contexts/UndoStore";
import { postUndoState } from "../shims/bridge";
import { isEditing } from "../utils/editing";
import { isEmbedded } from "../utils/embedded";

export function UndoSync() {
  const { t } = useTranslation();
  const state = useUndoState();
  const embedded = isEmbedded();

  useEffect(() => {
    if (!embedded) return;
    const undoLabel = state.undoAction ? t(`undo.undo.${state.undoAction}`) : null;
    const redoLabel = state.redoAction ? t(`undo.redo.${state.redoAction}`) : null;
    postUndoState(state.canUndo, state.canRedo, undoLabel, redoLabel);
  }, [embedded, state, t]);

  useEffect(() => {
    const onMenu = (e: Event) => {
      const action = (e as CustomEvent<{ action: string }>).detail?.action;
      if (action === "undo") void undo();
      else if (action === "redo") void redo();
    };
    window.addEventListener("bn:menu-action", onMenu);
    return () => window.removeEventListener("bn:menu-action", onMenu);
  }, []);

  useEffect(() => {
    if (embedded) return;
    // Reads the store at key time, not render state, so a key pressed
    // between a push and the re-render still sees the entry.
    const onKey = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || e.altKey || isEditing()) return;
      const key = e.key.toLowerCase();
      const wantsRedo = (key === "z" && e.shiftKey) || (key === "y" && e.ctrlKey && !e.metaKey);
      const wantsUndo = key === "z" && !e.shiftKey;
      if (wantsUndo && getUndoState().canUndo) {
        e.preventDefault();
        void undo();
      } else if (wantsRedo && getUndoState().canRedo) {
        e.preventDefault();
        void redo();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [embedded]);

  const runId = useLastRun().lastRun?.run_id ?? null;
  const seenRun = useRef<string | null>(null);
  useEffect(() => {
    if (runId === null) return;
    if (seenRun.current !== null && seenRun.current !== runId) clearUndo();
    seenRun.current = runId;
  }, [runId]);

  return null;
}
