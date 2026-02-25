/**
 * toast() — imperative toast function callable from anywhere.
 *
 * Manages a detached React root on a persistent container div.
 * One toast at a time — new calls replace the current.
 * Drop-in replacement for the vanilla showToast().
 */

import { createRoot } from "react-dom/client";
import type { Root } from "react-dom/client";
import { createElement } from "react";
import { Toast } from "../components/Toast";

let root: Root | null = null;
let container: HTMLDivElement | null = null;

function getContainer(): HTMLDivElement {
  if (!container) {
    container = document.createElement("div");
    container.setAttribute("data-testid", "bn-toast-container");
    document.body.appendChild(container);
  }
  return container;
}

function getRoot(): Root {
  if (!root) {
    root = createRoot(getContainer());
  }
  return root;
}

function dismiss(): void {
  getRoot().render(null);
}

/**
 * Show a toast notification. Only one visible at a time.
 *
 * @param message  Text to display
 * @param duration Auto-dismiss delay in ms (default 2000)
 */
export function toast(message: string, duration = 2000): void {
  getRoot().render(createElement(Toast, { message, duration, onDismiss: dismiss }));
}
