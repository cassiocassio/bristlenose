/**
 * Which lens a report path is on, in the two spellings AppLayout needs: the
 * Swift `Tab` rawValue the bridge reports (`getActiveTab`), and the label the
 * screen reader hears after a navigation ("Navigated to Quotes").
 *
 * Pulled out of AppLayout so both can be tested without mounting the shell.
 * A lens missing here is not an error anywhere: it falls through to the
 * Project lens, which is how the Screens lens came to be announced as
 * "Project" (14 Oct 2026).
 */
import i18n from "../i18n";

/** The `Tab` rawValue for a path (desktop/Bristlenose/Bristlenose/Tab.swift). */
export function activeTabForPath(path: string): string {
  if (path.startsWith("/report/quotes")) return "quotes";
  if (path.startsWith("/report/sessions")) return "sessions";
  if (path.startsWith("/report/codebook")) return "codebook";
  if (path.startsWith("/report/signals")) return "signals";
  if (path.startsWith("/report/discussion")) return "discussion";
  if (path.startsWith("/report/screens")) return "screens";
  return "project";
}

/** What "Navigated to …" names for a path. */
export function navigationLabel(path: string): string {
  let key = "nav.project";
  if (path.startsWith("/report/screens")) key = "nav.screens";
  else if (path.startsWith("/report/quotes")) key = "nav.quotes";
  else if (path.startsWith("/report/sessions/s")) key = "announce.transcript";
  else if (path.startsWith("/report/sessions")) key = "nav.sessions";
  // The codebook lens shares `nav.codebook` across its routes: it IS the
  // codebook lens, so the announcement is accurate.
  else if (path.startsWith("/report/codebook")) key = "nav.codebook";
  else if (path.startsWith("/report/signals")) key = "nav.signals";
  else if (path.startsWith("/report/discussion")) key = "nav.discussion";
  return i18n.t(key);
}
