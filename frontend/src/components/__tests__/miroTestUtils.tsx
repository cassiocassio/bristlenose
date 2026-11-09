/**
 * Send to Miro opens on the Miro app tab (owner, 9 Nov 2026). The token route's tests render the
 * panel and go to its tab first, as a researcher with a developer token would.
 */
import type { ReactElement } from "react";
import { fireEvent, render, screen } from "@testing-library/react";

export function renderOnTokenTab(ui: ReactElement): ReturnType<typeof render> {
  const result = render(ui);
  fireEvent.click(screen.getByTestId("bn-miro-tab-token"));
  return result;
}
