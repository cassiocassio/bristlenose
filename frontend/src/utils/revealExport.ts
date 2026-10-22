/**
 * Show a finished clips or screens export in Finder — the activity chip's Reveal.
 *
 * In the Mac app the sidecar runs inside the App Sandbox, so the server's `open -R`
 * does nothing there (R72). The app reveals through its own `reveal-in-finder`
 * project action instead, as the Sessions grid's folder link already does: Finder
 * performs the reveal in its own process, so no grant is needed. In a browser the
 * server's reveal route is the only way, and stays.
 */

import i18n from "../i18n";
import { isEmbedded } from "./embedded";
import { toast } from "./toast";
import { postProjectAction } from "../shims/bridge";
import {
  getClipExtractionStatus,
  getScreensExportStatus,
  revealClips,
  revealScreens,
} from "./api";

/** An absolute POSIX path as a `file:` URI, each component percent-encoded. */
export function fileUri(path: string): string {
  // A relative path would read its first component as the URI's host.
  if (!path.startsWith("/")) throw new Error(`not an absolute path: ${path}`);
  return "file://" + path.split("/").map(encodeURIComponent).join("/");
}

/** Where the export is: the clips folder, or the first still (the folder if none). */
async function exportTarget(kind: "clips" | "screens"): Promise<string | null> {
  // Only a finished export: the slot holds the latest job, which a newer export may
  // have replaced since the chip finished.
  if (kind === "clips") {
    const c = await getClipExtractionStatus();
    return c.status === "completed" ? c.output_dir : null;
  }
  const s = await getScreensExportStatus();
  if (s.status !== "completed" || !s.output_dir) return null;
  const first = s.files[0];
  return first ? `${s.output_dir.replace(/\/+$/, "")}/${first}` : s.output_dir;
}

export async function revealExport(kind: "clips" | "screens"): Promise<void> {
  if (!isEmbedded()) {
    const r = await (kind === "clips" ? revealClips() : revealScreens());
    if (!r.revealed) throw new Error(`the server could not show ${r.path}`);
    return;
  }
  const target = await exportTarget(kind);
  if (!target) {
    throw new Error(`no finished ${kind} export to reveal`);
  }
  postProjectAction("reveal-in-finder", { uri: fileUri(target) });
}

/**
 * The chip's Show in folder: reveal, and say so when it could not. The chip has
 * already closed, so a failure the console alone heard looked like nothing
 * happening (RE#20, decision #44). In the app a reveal the native side refuses
 * is not seen here; only one that never got that far.
 */
export async function revealExportOrSay(kind: "clips" | "screens"): Promise<void> {
  try {
    await revealExport(kind);
  } catch (err) {
    console.error(`Reveal ${kind} failed:`, err);
    toast(i18n.t("export.revealFailed"), 6000);
  }
}
