/**
 * PlaygroundFab — tiny floating button to open the Responsive Playground.
 *
 * Portal-rendered to document.body so it survives route changes.
 * Hidden when the playground drawer is already open.
 *
 * @module PlaygroundFab
 */

import { createPortal } from "react-dom";
import {
  usePlaygroundStore,
  togglePlayground,
} from "../contexts/PlaygroundStore";

export function PlaygroundFab() {
  const { open } = usePlaygroundStore();
  if (open) return null;

  return createPortal(
    <button
      className="pg-fab"
      onClick={togglePlayground}
      title="Responsive Playground (Ctrl+Shift+P)"
      aria-label="Open responsive playground"
      data-testid="pg-fab"
    >
      ◆
    </button>,
    document.body,
  );
}
