import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CodebookV2UninstallSheet } from "./CodebookV2UninstallSheet";
import type { RemoveFrameworkInfo } from "../utils/types";

const impact = (over: Partial<RemoveFrameworkInfo> = {}): RemoveFrameworkInfo => ({
  tag_count: 36,
  quote_count: 72,
  has_autocode: true,
  ...over,
});

const noop = () => {};
const renderSheet = (i: RemoveFrameworkInfo | null, impactFailed = false) =>
  render(
    <CodebookV2UninstallSheet
      title="10 Usability Heuristics"
      impact={i}
      impactFailed={impactFailed}
      onCancel={noop}
      onConfirm={noop}
    />,
  );

describe("a terse modal measures", () => {
  it("counts what goes, rather than warning", () => {
    renderSheet(impact());
    expect(screen.getByText(/36 tags/)).toBeInTheDocument();
    expect(screen.getByText(/tags on 72 quotes/)).toBeInTheDocument();
    // "This cannot be undone" tells a researcher nothing they can weigh.
    expect(screen.queryByText(/cannot be undone/i)).not.toBeInTheDocument();
  });

  it("names the AutoCode run, which the shipped copy does not", () => {
    // D20 option A made uninstall destroy the run as well as the tags. The
    // shipped line — "Tags will be removed from N quotes" — was accurate under
    // the old preserving model and understates this one.
    renderSheet(impact());
    expect(screen.getByText(/AutoCode run and every proposal/)).toBeInTheDocument();
  });

  it("omits a zero-count line rather than printing a nought", () => {
    renderSheet(impact({ quote_count: 0, has_autocode: false }));
    expect(screen.queryByText(/0 quote/)).not.toBeInTheDocument();
    expect(screen.getByText(/36 tags/)).toBeInTheDocument();
  });

  it("says so plainly when there is nothing to lose", () => {
    renderSheet(impact({ tag_count: 0, quote_count: 0, has_autocode: false }));
    expect(screen.getByText(/nothing is lost/)).toBeInTheDocument();
  });

  it("points at disable as the reversible verb", () => {
    // The whole reason uninstall can afford to be destructive (D20).
    renderSheet(impact());
    expect(screen.getByText(/switch it off instead/)).toBeInTheDocument();
  });

  it("opens before the counts arrive", () => {
    // Blocking on the impact fetch would make a destructive confirmation feel
    // laggy, which is the wrong thing to teach about it.
    renderSheet(null);
    expect(screen.getByTestId("bn-v2-uninstall-sheet")).toBeInTheDocument();
  });
});

describe("the buttons follow the HIG", () => {
  it("puts Cancel leading and the confirm trailing", () => {
    const { container } = renderSheet(impact());
    const buttons = [...container.querySelectorAll(".bn-modal-actions button")];
    expect(buttons[0]).toHaveTextContent("Cancel");
    expect(buttons[1]).toHaveTextContent("Uninstall");
  });

  it("does not make Cancel the default", () => {
    // Apple's guidance, and the correction the re-analyse sheet needed: Cancel
    // led AND held the default while the confirm carried .destructive — three
    // departures with one cause.
    renderSheet(impact());
    expect(screen.getByTestId("bn-v2-uninstall-cancel")).not.toHaveFocus();
    expect(screen.getByTestId("bn-v2-uninstall-confirm")).toHaveFocus();
  });

  it("does not style the confirm as destructive", () => {
    // .destructive is reserved for an action the researcher did NOT
    // deliberately choose. They clicked Uninstall.
    renderSheet(impact());
    expect(screen.getByTestId("bn-v2-uninstall-confirm").className).not.toContain(
      "danger",
    );
  });
});

describe("what the sheet knows, and what it only assumes", () => {
  // The counts arrive AFTER the sheet opens, so `impact === null` is two
  // different facts wearing one shape. Rendering both as "nothing is lost"
  // was a reassurance the sheet had not earned, on the one screen whose whole
  // job is to let a researcher weigh a destructive act.

  it("does not claim nothing is lost while it is still counting", () => {
    renderSheet(null);
    expect(screen.queryByText(/nothing is lost/)).toBeNull();
    expect(screen.getByTestId("bn-v2-uninstall-counting")).toBeInTheDocument();
  });

  it("does not claim nothing is lost when the count FAILED", () => {
    // THE bug. `onAskUninstall` used to `.catch(() => {})`, so a failed impact
    // fetch left `impact` null forever and the sheet said, in as many words,
    // that nothing would be lost. Confirming from that screen could discard a
    // fully coded framework.
    renderSheet(null, true);
    expect(screen.queryByText(/nothing is lost/)).toBeNull();
    expect(screen.getByTestId("bn-v2-uninstall-unknown")).toBeInTheDocument();
  });

  it("warns that coded work would go with it when it cannot check", () => {
    // Saying "couldn't check" and stopping there is only half honest — the
    // researcher still has to decide. Name the risk they are accepting.
    renderSheet(null, true);
    expect(screen.getByText(/that work goes with it/)).toBeInTheDocument();
  });

  it("still says nothing is lost when a measurement says so", () => {
    // The fix must not mute the true case — that would trade a false alarm
    // for a useless sheet.
    renderSheet(impact({ tag_count: 0, quote_count: 0, has_autocode: false }));
    expect(screen.getByTestId("bn-v2-uninstall-nothing")).toBeInTheDocument();
    expect(screen.getByText(/nothing is lost/)).toBeInTheDocument();
  });

  it("still lists real losses when it has them", () => {
    renderSheet(impact());
    expect(screen.queryByTestId("bn-v2-uninstall-nothing")).toBeNull();
    expect(screen.queryByTestId("bn-v2-uninstall-unknown")).toBeNull();
    expect(screen.getByText(/This will be discarded/)).toBeInTheDocument();
  });

  it("keeps the reinstall warning in every state", () => {
    // It is true regardless of what the counts said, and it is the line that
    // steers the researcher toward the reversible verb.
    for (const [i, failed] of [
      [null, false],
      [null, true],
      [impact({ tag_count: 0, quote_count: 0, has_autocode: false }), false],
    ] as const) {
      const { unmount } = renderSheet(i, failed);
      expect(screen.getByText(/costs a fresh run/)).toBeInTheDocument();
      unmount();
    }
  });
});
