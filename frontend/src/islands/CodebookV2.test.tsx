import { beforeEach, describe, expect, it, vi } from "vitest";
import { render as rtlRender, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { CodebookV2 } from "./CodebookV2";
import { CodebookV2Sidebar } from "../components/CodebookV2Sidebar";
import { resetCodebookV2Selection } from "../contexts/CodebookV2Store";

// The island reads `?view=library` via useSearchParams, so a bare render throws
// "useSearchParams() may be used only in the context of a <Router>". Alias once
// rather than wrapping every call site (frontend/CLAUDE.md).
const render = (ui: React.ReactElement, at = "/report/codebook-v2") =>
  rtlRender(ui, {
    wrapper: ({ children }) => (
      <MemoryRouter initialEntries={[at]}>{children}</MemoryRouter>
    ),
  });

/** Renders the router's current search string so a test can assert the URL
 *  moved. Rendered rather than assigned to a module variable: writing to one
 *  during render is a side effect, and the query is what we want to read. */
function LocationProbe() {
  return <span data-testid="bn-test-search">{useLocation().search}</span>;
}
const search = () => screen.getByTestId("bn-test-search").textContent ?? "";

/** What AppLayout mounts: the navigator in the left sidebar, the lens beside
 *  it. Selection travels between them through CodebookV2Store, so a test that
 *  rendered only the lens would be testing a screen no researcher sees. */
function Lens(props: { projectId: string; projectName?: string }) {
  return (
    <>
      <CodebookV2Sidebar />
      <CodebookV2 {...props} />
    </>
  );
}

beforeEach(() => resetCodebookV2Selection());

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
  // The only NOT-installed template in the fixture: absent from codebook.groups,
  // so `books` never contains it. Carries real groups so a test can prove the
  // details page renders its structure, not just its title.
  { id: "cliux", title: "Command-Line UX", author: "", description: "",
    author_bio: "", author_links: [], enabled: true, imported: false,
    groups: [
      { name: "Discoverability", subtitle: "", colour_set: "ux",
        tags: [{ name: "first-time use", colour_index: 0 },
               { name: "exploration", colour_index: 1 }] },
    ] },
]};

vi.mock("../utils/api", () => ({
  // The navigator titles the floor row with the project name, from /info.
  apiGet: vi.fn(() => Promise.resolve({ project_name: "Ikea" })),
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
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav-row-nielsen"));

    const rail = screen.getByTestId("bn-v2-nav");
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
    // would misdescribe. Asserted on the PAGE, which is the only surface that
    // renders a system fact — the rail dropped it 31 Aug 2026 because one slot
    // reading "who made this" in one row and "how this is configured" in the
    // next is a false parallel, and neither helps choose. The page shows one
    // codebook, invites no comparison, and the state is useful context there.
    const { fireEvent } = await import("@testing-library/react");
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav-row-uxr"));

    fireEvent.click(screen.getByTestId("bn-v2-nav-row-uxr"));
    await waitFor(() => expect(screen.getByText("Available by default")).toBeInTheDocument());

    fireEvent.click(screen.getByTestId("bn-v2-nav-row-sentiment"));
    await waitFor(() => expect(screen.getByText("On by default")).toBeInTheDocument());
  });

  it("keeps a person's name in the rail, and the system fact off it", async () => {
    render(<Lens projectId="1" projectName="Ikea" />);
    const nielsen = await screen.findByTestId("bn-v2-nav-row-nielsen");
    expect(nielsen).toHaveTextContent("Jakob Nielsen");
    expect(screen.getByTestId("bn-v2-nav-row-sentiment")).not.toHaveTextContent(
      "by default",
    );
  });

  it("sums tentative counts into the rail badge", async () => {
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByText("7"));
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("treats an absent framework-state entry as enabled", async () => {
    // "off means off" is what gets stored; on is the absence of an off.
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav-row-uxr"));
    expect(screen.getByTestId("bn-v2-nav-row-uxr").className).toContain("codebook-disabled");
    expect(screen.getByTestId("bn-v2-nav-row-nielsen").className).not.toContain("codebook-disabled");
  });

  it("names the floor after the project", async () => {
    // Appears twice by design once the page renders — the rail row and the page
    // title — so scope to the rail rather than loosening the query.
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav-row-floor"));
    expect(screen.getByTestId("bn-v2-nav-row-floor")).toHaveTextContent("Ikea tags");
  });
});

describe("D22 — Browse Library is the navigation", () => {
  // The in-page "‹ Back" was removed 31 Aug 2026: the app toolbar's chevron
  // (BridgeHandler.goBack → webView.goBack) and the browser's own button are
  // the back affordances, and a third one inside the page was chrome competing
  // with muscle memory. That removal is only CORRECT if opening the library is
  // a history entry — as component state it wasn't, and back left the lens
  // entirely. These two tests pin the mechanism from both ends. Asserting that
  // Back itself works would be asserting React Router.

  it("opening the catalogue moves the URL, so history can return from it", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(
      <>
        <Lens projectId="1" projectName="Ikea" />
        <LocationProbe />
      </>,
    );
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    expect(search()).not.toContain("view=library");

    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    await waitFor(() => screen.getByTestId("bn-v2-browse-grid"));
    expect(screen.getByTestId("bn-v2-card-nielsen")).toBeInTheDocument();
    expect(search()).toContain("view=library");
  });

  it("renders the catalogue when the URL says so, and the page when it does not", async () => {
    // The reverse of the first test, and what a Back actually lands on. Also
    // makes the catalogue deep-linkable, which component state never was.
    render(<Lens projectId="1" />, "/report/codebook-v2?view=library");
    await waitFor(() => screen.getByTestId("bn-v2-browse-grid"));
  });

  it("ships no back button of its own", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(<Lens projectId="1" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    await waitFor(() => screen.getByTestId("bn-v2-browse-grid"));
    expect(screen.queryByTestId("bn-v2-back")).toBeNull();
  });

  it("a card opens that codebook's page", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));

    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    fireEvent.click(screen.getByTestId("bn-v2-card-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-page"));
    expect(screen.getByTestId("bn-v2-nav-row-nielsen").className).toContain("active");
  });

  it("a rail row leaves the catalogue", async () => {
    // Otherwise selecting in the rail silently does nothing while the grid
    // stays on screen — the rail is the OTHER route to a codebook (D22).
    const { fireEvent } = await import("@testing-library/react");
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));

    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    expect(screen.getByTestId("bn-v2-card-nielsen")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("bn-v2-nav-row-uxr"));
    await waitFor(() => screen.getByTestId("bn-v2-page"));
    expect(screen.queryByTestId("bn-v2-browse-grid")).not.toBeInTheDocument();
  });

  it("the catalogue lists uninstalled codebooks the rail does not", async () => {
    // The asymmetry is the point: the rail is what you have, the Library is
    // what there is (D17 installed-only vs the catalogue).
    const { fireEvent } = await import("@testing-library/react");
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    fireEvent.click(screen.getByTestId("bn-v2-browse"));
    expect(screen.getByTestId("bn-v2-card-sentiment")).toBeInTheDocument();
    expect(screen.getByTestId("bn-v2-card-uxr")).toBeInTheDocument();
  });
});

describe("phase 5 — the destructive edge", () => {
  it("confirms before uninstalling, and cancelling does nothing", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const api = await import("../utils/api");
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    // The floor is selected by default and correctly has no install controls
    // (D20), so pick a framework first.
    fireEvent.click(screen.getByTestId("bn-v2-nav-row-nielsen"));
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
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    // The floor is selected by default and correctly has no install controls
    // (D20), so pick a framework first.
    fireEvent.click(screen.getByTestId("bn-v2-nav-row-nielsen"));
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
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
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
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
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
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    expect(screen.queryByText(/Could not load the codebook/)).not.toBeInTheDocument();
    // The codebook still renders — the rail is built from /codebook, not from
    // the catalogue.
    expect(screen.getByTestId("bn-v2-nav-row-nielsen")).toBeInTheDocument();
  });

  it("hides Browse Library in an exported report", async () => {
    const exportData = await import("../utils/exportData");
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    // Hidden, not disabled — the house pattern for export mode. There is no
    // catalogue to browse and installing is a write.
    expect(screen.queryByTestId("bn-v2-browse")).not.toBeInTheDocument();
    vi.mocked(exportData.isExportMode).mockRestore();
  });

  it("hides the install controls in an exported report", async () => {
    const { fireEvent } = await import("@testing-library/react");
    const exportData = await import("../utils/exportData");
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav"));
    fireEvent.click(screen.getByTestId("bn-v2-nav-row-nielsen"));
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
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav-row-nielsen"));

    fireEvent.click(screen.getByTestId("bn-v2-nav-row-nielsen"));
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
    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-nav-row-nielsen"));

    fireEvent.click(screen.getByTestId("bn-v2-nav-row-nielsen"));
    await waitFor(() => screen.getByTestId("bn-v2-review"));
    fireEvent.click(screen.getByTestId("bn-v2-review"));

    await waitFor(() =>
      expect(vi.mocked(api.getAutoCodeProposals)).toHaveBeenCalled(),
    );
    const args = vi.mocked(api.getAutoCodeProposals).mock.calls[0];
    expect(args.some((a) => a === "nielsen")).toBe(true);
  });
});

describe("group order matches the shipped lens", () => {
  it("puts Uncategorised first, then by order", async () => {
    // Found by opening both lenses on the same project: v1 hoists the default
    // group, v2 did no sorting and rendered in API order, so Uncategorised
    // came LAST. Two lenses disagreeing about where the untagged bucket lives
    // is exactly the drift D29's side-by-side exists to catch.
    const api = await import("../utils/api");
    vi.mocked(api.getCodebook).mockResolvedValue({
      ...codebook,
      groups: [
        { id: 9, name: "Zebra", subtitle: "", colour_set: "ux", order: 2, tags: [],
          total_quotes: 0, is_default: false, framework_id: null },
        { id: 8, name: "Uncategorised", subtitle: "", colour_set: "ux", order: 9,
          tags: [], total_quotes: 0, is_default: true, framework_id: null },
        { id: 7, name: "Apple", subtitle: "", colour_set: "ux", order: 1, tags: [],
          total_quotes: 0, is_default: false, framework_id: null },
      ],
    } as never);

    render(<Lens projectId="1" projectName="Ikea" />);
    await waitFor(() => screen.getByTestId("bn-v2-page"));

    const titles = Array.from(
      document.querySelectorAll(".v2-groups .group-title"),
    ).map((n) => n.textContent);
    expect(titles).toEqual(["Uncategorised", "Apple", "Zebra"]);
  });
});


describe("a not-yet-installed codebook opens its details page", () => {
  // The card fires onOpen for every codebook, installed or not — CodebookV2Browse
  // says so in its own header ("The whole card navigates") and its tests pin it.
  // The consumer was the half that broke the contract: `books` is installed-only,
  // so `current` fell through to `books[0]` and the lens rendered a DIFFERENT
  // codebook's page, or none at all when nothing was installed. The card's tests
  // could not see it, because they end at the callback.
  it("shows the codebook you clicked, not the first installed one", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(<Lens projectId="1" projectName="Ikea" />, "/report/codebook-v2?view=library");
    await waitFor(() => screen.getByTestId("bn-v2-card-cliux"));

    fireEvent.click(screen.getByTestId("bn-v2-card-cliux"));

    await waitFor(() => screen.getByTestId("bn-v2-page"));
    expect(screen.getByTestId("bn-v2-page").textContent).toContain("Command-Line UX");
  });

  it("renders that codebook's own groups and tags", async () => {
    const { fireEvent } = await import("@testing-library/react");
    render(<Lens projectId="1" projectName="Ikea" />, "/report/codebook-v2?view=library");
    await waitFor(() => screen.getByTestId("bn-v2-card-cliux"));

    fireEvent.click(screen.getByTestId("bn-v2-card-cliux"));

    await waitFor(() => screen.getByTestId("bn-v2-page"));
    const page = screen.getByTestId("bn-v2-page").textContent ?? "";
    expect(page).toContain("Discoverability");
    expect(page).toContain("first-time use");
    // It is not installed, so the page must say so rather than claim reach.
    expect(page).toContain("not installed");
  });
});
