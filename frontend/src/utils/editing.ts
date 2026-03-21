/**
 * Editing state detection — true when the user is actively editing text.
 *
 * Used by keyboard shortcuts (to suppress bare-key shortcuts) and the
 * native bridge (to notify the macOS shell when Cmd+[ / Cmd+] should
 * be rerouted during inline editing).
 */

/**
 * Check if the user is currently editing (input, textarea, contenteditable,
 * or tag suggest active).  Keyboard shortcuts should not fire while editing.
 */
export function isEditing(): boolean {
  const el = document.activeElement;
  if (!el) return false;
  const tag = el.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA") return true;
  if ((el as HTMLElement).isContentEditable) return true;
  if (el.closest(".tag-suggest")) return true;
  return false;
}
