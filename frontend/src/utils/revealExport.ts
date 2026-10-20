/**
 * Show a finished clips or screens export in Finder — the activity chip's Reveal.
 *
 * In the Mac app the sidecar runs inside the App Sandbox, so the server's `open -R`
 * does nothing there (R72). The app reveals through its own `reveal-in-finder`
 * project action instead, as the Sessions grid's folder link already does: Finder
 * performs the reveal in its own process, so no grant is needed. In a browser the
 * server's reveal route is the only way, and stays.
 */

import { isEmbedded } from "./embedded";
import { postProjectAction } from "../shims/bridge";
import {
  getClipExtractionStatus,
  getScreensExportStatus,
  revealClips,
  revealScreens,
} from "./api";

/** A POSIX path as a `file:` URI, each component percent-encoded. */
export function fileUri(path: string): string {
  return "file://" + path.split("/").map(encodeURIComponent).join("/");
}

/** Where the export is: the clips folder, or the first still (the folder if none). */
async function exportTarget(kind: "clips" | "screens"): Promise<string | null> {
  if (kind === "clips") {
    return (await getClipExtractionStatus()).output_dir;
  }
  const s = await getScreensExportStatus();
  if (!s.output_dir) return null;
  const first = s.files[0];
  return first ? `${s.output_dir.replace(/\/+$/, "")}/${first}` : s.output_dir;
}

export async function revealExport(kind: "clips" | "screens"): Promise<void> {
  if (!isEmbedded()) {
    await (kind === "clips" ? revealClips() : revealScreens());
    return;
  }
  const target = await exportTarget(kind);
  if (!target) {
    throw new Error(`no finished ${kind} export to reveal`);
  }
  postProjectAction("reveal-in-finder", { uri: fileUri(target) });
}
