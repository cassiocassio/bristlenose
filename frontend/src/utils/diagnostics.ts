/**
 * Whether the researcher has asked for diagnostics.
 *
 * On the Mac the Diagnostics preference (Settings ▸ Appearance) injects
 * `window.__BRISTLENOSE_DIAGNOSTICS__` when the report view is built; `serve --dev`
 * turns it on in the browser. Never in an exported report: the numbers describe how
 * this machine heard the recordings, not the findings.
 */
import { isExportMode } from "./exportData";

export function diagnosticsEnabled(): boolean {
  if (isExportMode()) return false;
  const w = window as unknown as Record<string, unknown>;
  return w.__BRISTLENOSE_DIAGNOSTICS__ === true || w.__BRISTLENOSE_DEV__ === true;
}
