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

export const TocShowingContext = createContext(false);

export function useTocShowing(): boolean {
  return useContext(TocShowingContext);
}
