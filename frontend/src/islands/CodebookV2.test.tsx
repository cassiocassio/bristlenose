import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { CodebookV2 } from "./CodebookV2";

const codebook = {
  groups: [
    { id: 1, name: "Sentiment", subtitle: "", colour_set: "sentiment", order: 0,
      tags: [{ id: 1, name: "delight", count: 3, tentative_count: 0, colour_index: 0 }],
      total_quotes: 3, is_default: false, framework_id: "sentiment" },
    { id: 2, name: "Behaviour", subtitle: "", colour_set: "ux", order: 1,
      tags: [{ id: 2, name: "workaround", count: 5, tentative_count: 2, colour_index: 0 }],
      total_quotes: 5, is_default: false, framework_id: "uxr" },
    { id: 3, name: "Status visibility", subtitle: "", colour_set: "ux", order: 2,
      tags: [{ id: 3, name: "clear status", count: 4, tentative_count: 7, colour_index: 0 }],
      total_quotes: 4, is_default: false, framework_id: "nielsen" },
  ],
  ungrouped: [], all_tag_names: [], framework_quote_totals: {},
};
const templates = { templates: [
  { id: "sentiment", title: "Sentiment", author: "", description: "", author_bio: "",
    author_links: [], groups: [], enabled: true, imported: true },
  { id: "uxr", title: "Bristlenose UXR", author: "", description: "", author_bio: "",
    author_links: [], groups: [], enabled: true, imported: true },
  { id: "nielsen", title: "10 Usability Heuristics", author: "Jakob Nielsen",
    description: "", author_bio: "", author_links: [], groups: [], enabled: true,
    imported: true },
  { id: "cliux", title: "Command-Line UX", author: "", description: "",
    author_bio: "", author_links: [], groups: [], enabled: true, imported: false },
]};

vi.mock("../utils/api", () => ({
  getCodebook: vi.fn(() => Promise.resolve(codebook)),
  getCodebookTemplates: vi.fn(() => Promise.resolve(templates)),
  getFrameworkStates: vi.fn(() => Promise.resolve({ uxr: false })),
  putFrameworkStates: vi.fn(() => Promise.resolve({ status: "ok", catchUp: [] })),
  getRemoveFrameworkImpact: vi.fn(() =>
    Promise.resolve({ tag_count: 4, quote_count: 9, has_autocode: true }),
  ),
  removeCodebookFramework: vi.fn(() => Promise.resolve(codebook)),
  importCodebookTemplate: vi.fn(() => Promise.resolve(codebook)),
  startAutoCode: vi.fn(() => Promise.resolve({ status: "pending" })),
  // Q15's modal is the SHIPPED ThresholdReviewModal, which fetches on open.
  // A wholesale module mock hands it `undefined` for anything not listed here,
  // so the Review-door test would fail on the mock rather than on the door.
  getAutoCodeProposals: vi.fn(() => Promise.resolve({ proposals: [] })),
  acceptAllProposals: vi.fn(() => Promise.resolve({ accepted: 0 })),
  acceptProposal: vi.fn(() => Promise.resolve({ status: "ok" })),
  denyAllProposals: vi.fn(() => Promise.resolve({ denied: 0 })),
  denyProposal: vi.fn(() => Promise.resolve({ status: "ok" })),
}));
vi.mock("../contexts/ActivityStore", () => ({ addJob: vi.fn() }));

describe("CodebookV2 — built-in is derived, not hardcoded", () => {
  it("files authorless codebooks under Default and authored ones under Frameworks", async () => {
    // The signal is the ABSENCE OF AN AUTHOR, measured exact across the nine
    // shipped codebooks. A hardcoded id list would have filed the fourth
    // built-in under Frameworks silently, and nothing would have failed.
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail-row-nielsen"));

    const rail = screen.getByTestId("bn-v2-rail");
    const order = Array.from(rail.children).map((c) => c.textContent ?? "");
    const iDefault = order.findIndex((t) => t === "Default");
    const iFrameworks = order.findIndex((t) => t === "Frameworks");
    const iSentiment = order.findIndex((t) => t.includes("Sentiment"));
    const iNielsen = order.findIndex((t) => t.includes("Usability"));

    expect(iDefault).toBeGreaterThan(-1);
    expect(iSentiment).toBeGreaterThan(iDefault);
    expect(iSentiment).toBeLessThan(iFrameworks);
    expect(iNielsen).toBeGreaterThan(iFrameworks);
  });

  it("gives each built-in the provenance its state actually warrants", async () => {
    // Not cosmetic: UXR here is installed AND disabled, which "On by default"
    // would misdescribe.
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByText("On by default"));
    expect(screen.getByText("Available by default")).toBeInTheDocument();
    expect(screen.getByText("Jakob Nielsen")).toBeInTheDocument();
  });

  it("sums tentative counts into the rail badge", async () => {
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByText("7"));
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("treats an absent framework-state entry as enabled", async () => {
    // "off means off" is what gets stored; on is the absence of an off.
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail-row-uxr"));
    expect(screen.getByTestId("bn-v2-rail-row-uxr").className).toContain("off2");
    expect(screen.getByTestId("bn-v2-rail-row-nielsen").className).not.toContain("off2");
  });

  it("names the floor after the project", async () => {
    // Appears twice by design once the page renders — the rail row and the page
    // title — so scope to the rail rather than loosening the query.
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail-row-floor"));
    expect(screen.getByTestId("bn-v2-rail-row-floor")).toHaveTextContent("Ikea tags");
  });
});

describe("D22 — Browse Library is the navigation", () => {
  it("goes to the catalogue and back", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));

    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    await waitFor(() => screen.getByTestId("bn-v2-browse-grid"));
    expect(screen.getByTestId("bn-v2-card-nielsen")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("bn-v2-back"));
    await waitFor(() => screen.getByTestId("bn-v2-page"));
  });

  it("a card opens that codebook's page", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));

    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    fireEvent.click(screen.getByTestId("bn-v2-card-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-page"));
    expect(screen.getByTestId("bn-v2-rail-row-nielsen").className).toContain("sel");
  });

  it("a rail row leaves the catalogue", async () => {
    // Otherwise selecting in the rail silently does nothing while the grid
    // stays on screen — the rail is the OTHER route to a codebook (D22).
    const { fireEvent } = await import("@testing-library/react");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));

    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    expect(screen.getByTestId("bn-v2-card-nielsen")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("bn-v2-rail-row-uxr"));
    await waitFor(() => screen.getByTestId("bn-v2-page"));
    expect(screen.queryByTestId("bn-v2-browse-grid")).not.toBeInTheDocument();
  });

  it("the catalogue lists uninstalled codebooks the rail does not", async () => {
    // The asymmetry is the point: the rail is what you have, the Library is
    // what there is (D17 installed-only vs the catalogue).
    const { fireEvent } = await import("@testing-library/react");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    expect(screen.getByTestId("bn-v2-card-sentiment")).toBeInTheDocument();
    expect(screen.getByTestId("bn-v2-card-uxr")).toBeInTheDocument();
  });
});

describe("phase 5 — the destructive edge", () => {
  it("confirms before uninstalling, and cancelling does nothing", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const api = await import("../utils/api");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    // The floor is selected by default and correctly has no install controls
    // (D20), so pick a framework first.
    fireEvent.click(screen.getByTestId("bn-v2-rail-row-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-uninstall"));

    fireEvent.click(screen.getByTestId("bn-v2-uninstall"));
    await waitFor(() => screen.getByTestId("bn-v2-uninstall-sheet"));
    // Nothing has happened yet — the sheet is a decision, not a receipt.
    expect(api.removeCodebookFramework).not.toHaveBeenCalled();

    fireEvent.click(screen.getByTestId("bn-v2-uninstall-cancel"));
    await waitFor(() =>
      expect(screen.queryByTestId("bn-v2-uninstall-sheet")).not.toBeInTheDocument(),
    );
    expect(api.removeCodebookFramework).not.toHaveBeenCalled();
  });

  it("uninstalls only after the confirm", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const api = await import("../utils/api");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    // The floor is selected by default and correctly has no install controls
    // (D20), so pick a framework first.
    fireEvent.click(screen.getByTestId("bn-v2-rail-row-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-uninstall"));

    fireEvent.click(screen.getByTestId("bn-v2-uninstall"));
    await waitFor(() => screen.getByTestId("bn-v2-uninstall-sheet"));
    fireEvent.click(screen.getByTestId("bn-v2-uninstall-confirm"));
    await waitFor(() => expect(api.removeCodebookFramework).toHaveBeenCalled());
  });

  it("install APPLIES — importing alone would code nothing (D4)", async () => {
    // Two calls, not one. The template import puts the tags in the codebook;
    // the job is what codes the quotes. Importing alone leaves the separate
    // Apply step v2 exists to remove, half-implemented and invisible.
    const { fireEvent } = await import("@testing-library/react");
    const api = await import("../utils/api");
    const store = await import("../contexts/ActivityStore");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    fireEvent.click(screen.getByTestId("bn-v2-card-action-cliux"));

    await waitFor(() => expect(api.startAutoCode).toHaveBeenCalledWith("cliux"));
    expect(api.importCodebookTemplate).toHaveBeenCalledWith("cliux");
    // And it registers with the chip stack: autotagging is not instant, so
    // without this the researcher clicks Install and nothing appears to happen.
    await waitFor(() => expect(store.addJob).toHaveBeenCalled());
  });

  it("installs without a confirmation", async () => {
    // Install IS apply (D4) and it spends — but the researcher asked by
    // clicking, and a dialog on an additive act teaches them to dismiss
    // dialogs, which is what makes the destructive one stop working.
    const { fireEvent } = await import("@testing-library/react");
    const api = await import("../utils/api");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    fireEvent.click(screen.getByTestId("bn-v2-card-action-cliux"));
    await waitFor(() => expect(api.importCodebookTemplate).toHaveBeenCalledWith("cliux"));
    expect(screen.queryByTestId("bn-v2-uninstall-sheet")).not.toBeInTheDocument();
  });
});

describe("Q14 — export mode's fourth state", () => {
  it("survives the templates route being server-only", async () => {
    // /codebook and /framework-states are embedded in an export;
    // /codebook/templates is not. A bare Promise.all rejects on that one and
    // blanks the whole lens — the reader of a leave-behind would get an error
    // where their codebook should be.
    const api = await import("../utils/api");
    vi.mocked(api.getCodebookTemplates).mockRejectedValueOnce(
      new Error("GET /codebook/templates: not embedded"),
    );
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    expect(screen.queryByText(/Could not load the codebook/)).not.toBeInTheDocument();
    // The codebook still renders — the rail is built from /codebook, not from
    // the catalogue.
    expect(screen.getByTestId("bn-v2-rail-row-nielsen")).toBeInTheDocument();
  });

  it("hides Browse Library in an exported report", async () => {
    const exportData = await import("../utils/exportData");
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    // Hidden, not disabled — the house pattern for export mode. There is no
    // catalogue to browse and installing is a write.
    expect(screen.queryByTestId("bn-v2-browse")).not.toBeInTheDocument();
    vi.mocked(exportData.isExportMode).mockRestore();
  });

  it("hides the install controls in an exported report", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const exportData = await import("../utils/exportData");
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail"));
    fireEvent.click(screen.getByTestId("bn-v2-rail-row-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-page"));
    expect(screen.queryByTestId("bn-v2-uninstall")).not.toBeInTheDocument();
    vi.mocked(exportData.isExportMode).mockRestore();
  });
});

describe("CodebookV2 — the Review door (Q15)", () => {
  it("opens the SHIPPED threshold modal, not a v2 rebuild", async () => {
    // The door was inert for three phases: the handler was an empty arrow with
    // a comment saying phase 5 would wire it. A control that looks live and
    // does nothing is worse than one that isn't there, and it is invisible to
    // every test that only asserts the button renders.
    const { fireEvent } = await import("@testing-library/react");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail-row-nielsen"));

    fireEvent.click(screen.getByTestId("bn-v2-rail-row-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-review"));

    // The shipped modal is always MOUNTED and gates on `open` — it portals to
    // document.body with `aria-hidden={!open}`. So "closed" is an attribute,
    // not an absent node; asserting absence passes for the wrong reason and
    // would keep passing if the door were re-broken.
    const overlay = () =>
      screen.getByTestId("bn-threshold-subtitle").closest(".codebook-modal-overlay");
    expect(overlay()?.getAttribute("aria-hidden")).toBe("true");

    fireEvent.click(screen.getByTestId("bn-v2-review"));

    // Presence of the shipped modal's own element is also the proof it is that
    // component and not a v2 lookalike, which Q15 rules out.
    await waitFor(() => expect(overlay()?.getAttribute("aria-hidden")).toBe("false"));
    expect(overlay()?.className).toContain("visible");
  });

  it("asks the modal about the codebook whose door was clicked", async () => {
    // A door that opens the modal for the wrong framework is the failure mode
    // a smoke test misses — the modal renders either way.
    const { fireEvent } = await import("@testing-library/react");
    const api = await import("../utils/api");
    render(<CodebookV2 projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-rail-row-nielsen"));

    fireEvent.click(screen.getByTestId("bn-v2-rail-row-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-review"));
    fireEvent.click(screen.getByTestId("bn-v2-review"));

    await waitFor(() =>
      expect(vi.mocked(api.getAutoCodeProposals)).toHaveBeenCalled(),
    );
    const args = vi.mocked(api.getAutoCodeProposals).mock.calls[0];
    expect(args.some((a) => a === "nielsen")).toBe(true);
  });
});
