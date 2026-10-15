/**
 * Whether the content sidebar is showing as a resting panel — what the grid
 * actually draws, as `SidebarLayout` fits the wish to the width.
 *
 * `SidebarLayout` is the one owner of that answer and provides it to the page
 * it wraps. Reading it here rather than recomputing `panelFit()` keeps a lens
 * that moves a control between the sidebar and the page in step with the grid:
 * the two calculations differ (the layout's right column comes from its prop,
 * the store's from a later effect), and a control placed by the other one could
 * end up in neither place. The hover peek is not a resting panel and reads false.
 */

import { createContext, useContext } from "react";
import type { BarMode } from "./SidebarStore";

export const TocShowingContext = createContext(false);

export function useTocShowing(): boolean {
  return useContext(TocShowingContext);
}

/**
 * Where the browser tab bar sits in the same fit: full spacing, condensed, or
 * condensed with its icons moved into the report header. SidebarLayout is the
 * owner here too; NavBar and Header read it. Default "full" (no layout above).
 */
export const NavBarModeContext = createContext<BarMode>("full");

export function useNavBarMode(): BarMode {
  return useContext(NavBarModeContext);
}
