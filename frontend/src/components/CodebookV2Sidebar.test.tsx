import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter, useLocation } from "react-router-dom";
import { CodebookV2Sidebar, buildBooks, type V2NavBook } from "./CodebookV2Sidebar";
import {
  resetCodebookV2Selection,
  selectCodebookV2,
} from "../contexts/CodebookV2Store";
import type { CodebookResponse, TemplateListResponse } from "../utils/types";

const group = (over: Record<string, unknown> = {}) =>
  ({
    id: 1, name: "G", subtitle: "", colour_set: "ux", order: 0, tags: [],
    total_quotes: 0, is_default: false, framework_id: null, ...over,
  }) as never;

const codebook = {
  groups: [
    group({ id: 1, name: "Pain", framework_id: null, tags: [{ id: 1, name: "a", count: 1, tentative_count: 0, colour_index: 0 }] }),
    group({ id: 2, name: "Sentiment", framework_id: "sentiment", tags: [{ id: 2, name: "b", count: 1, tentative_count: 2, colour_index: 0 }] }),
    group({ id: 3, name: "Heuristics", framework_id: "nielsen", tags: [{ id: 3, name: "c", count: 1, tentative_count: 5, colour_index: 0 }] }),
  ],
  ungrouped: [], all_tag_names: [], framework_quote_totals: {},
} as unknown as CodebookResponse;

const templates = {
  templates: [
    { id: "sentiment", title: "Emotional & Cognitive Signals", author: "", description: "", author_bio: "", author_links: [], groups: [], enabled: true, imported: true },
    { id: "nielsen", title: "10 Usability Heuristics", author: "Jakob Nielsen", description: "", author_bio: "", author_links: [], groups: [], enabled: true, imported: true },
    { id: "cliux", title: "Command-Line UX", author: "", description: "", author_bio: "", author_links: [], groups: [], enabled: true, imported: false },
  ],
} as unknown as TemplateListResponse;

vi.mock("../utils/api", () => ({
  apiGet: vi.fn(() => Promise.resolve({ project_name: "Ikea" })),
  getCodebook: vi.fn(() => Promise.resolve(codebook)),
  getCodebookTemplates: vi.fn(() => Promise.resolve(templates)),
  getFrameworkStates: vi.fn(() => Promise.resolve({ nielsen: false })),
  putFrameworkStates: vi.fn(() => Promise.resolve({ status: "ok", catchUp: [] })),
}));

beforeEach(() => resetCodebookV2Selection());

// The navigator reads and writes the `?view=library` search param (Browse
// Library), so it needs router context. `initialEntries` matches the route
// AppLayout actually mounts it on.
function LocationProbe() {
  const loc = useLocation();
  return <span data-testid="loc-search">{loc.search}</span>;
}

const renderSidebar = (entry = "/report/codebook-v2") =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <CodebookV2Sidebar />
      <LocationProbe />
    </MemoryRouter>,
  );

// ── The house typography, not a v2 dialect ─────────────────────────────────

describe("it is the standard content navigator", () => {
  // v2 shipped its navigation as a `<nav class="v2-rail">` inside the lens's
  // content column, restating padding, radius, hover and selection from
  // scratch — and losing the toolbar toggle, the `[` key, drag-to-resize,
  // hover-peek and the panel-state bridge post, none of which is
  // reimplementable per-lens.

  it("uses the shipped row and heading classes", async () => {
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-floor");

    // `.toc-link` carries the metrics; `.codebook-toc-link` the codebook
    // variant. Both come from theme/organisms/sidebar.css.
    const row = screen.getByTestId("bn-v2-nav-row-nielsen");
    expect(row.className).toContain("toc-link");
    expect(row.className).toContain("codebook-toc-link");

    // Section headings are `.toc-heading`, as in CodebookSidebar.
    expect(document.querySelectorAll(".toc-heading").length).toBe(3);
  });

  it("marks the selected row `active`, not a v2-only modifier", async () => {
    // THE COLOUR. The rail used `--bn-colour-active-bg` — `#f0fdf4`, the
    // palette's *success* background — so the current codebook rendered mint
    // green. `.toc-link.active` is `--bn-nav-selection-bg`, a neutral grey.
    // Selection is not success.
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-nielsen");

    act(() => selectCodebookV2("nielsen"));
    await waitFor(() =>
      expect(screen.getByTestId("bn-v2-nav-row-nielsen").className).toContain("active"),
    );
    expect(screen.getByTestId("bn-v2-nav-row-nielsen").className).not.toContain("sel");
    expect(screen.getByTestId("bn-v2-nav-row-floor").className).not.toContain("active");
  });

  it("uses the shipped disabled modifier for a switched-off codebook", async () => {
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-nielsen");
    // getFrameworkStates says nielsen is off.
    expect(screen.getByTestId("bn-v2-nav-row-nielsen").className).toContain(
      "codebook-disabled",
    );
    expect(screen.getByTestId("bn-v2-nav-row-sentiment").className).not.toContain(
      "codebook-disabled",
    );
  });

  it("announces itself and its current row to assistive tech", async () => {
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-floor");
    expect(screen.getByRole("navigation", { name: "Codebooks" })).toBeInTheDocument();

    act(() => selectCodebookV2("nielsen"));
    await waitFor(() =>
      expect(screen.getByTestId("bn-v2-nav-row-nielsen")).toHaveAttribute(
        "aria-current",
        "location",
      ),
    );
  });
});

// ── The switch, at the size we settled on ─────────────────────────────────

describe("the second line is a person, or nothing", () => {
  // The slot held "On by default" / "Available by default" too. In a LIST the
  // eye reads the second line as one slot with one meaning, and two rows apart
  // it said "who made this" and "how this is configured" — a false parallel
  // however lightly it was set. It also cannot help choose: everything in this
  // rail is already installed, so "Available by default" is not actionable
  // here. The catalogue keeps it, where it distinguishes a Bristlenose codebook
  // from a third party's and IS decision-relevant.

  it("renders an author under a framework", async () => {
    renderSidebar();
    const row = await screen.findByTestId("bn-v2-nav-row-nielsen");
    expect(row).toHaveTextContent("Jakob Nielsen");
  });

  it("renders nothing under a built-in, collapsing the row to one line", async () => {
    renderSidebar();
    const row = await screen.findByTestId("bn-v2-nav-row-sentiment");
    expect(row).not.toHaveTextContent("On by default");
    expect(row.querySelector(".v2-nav-provenance")).toBeNull();
    // The title survives — this drops the second line, not the row.
    expect(row).toHaveTextContent("Emotional & Cognitive Signals");
  });

  it("leaves the floor with no second line either", async () => {
    renderSidebar();
    const row = await screen.findByTestId("bn-v2-nav-row-floor");
    expect(row.querySelector(".v2-nav-provenance")).toBeNull();
  });
});

describe("the enable switch rides on the row", () => {
  it("gives every codebook a switch except the floor", async () => {
    // The floor is not a codebook you can switch off — it is your own tags
    // (D20). Everything else gets one, because this rail is where a codebook
    // is turned on and off; the shipped navigator's status dot only reports.
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-floor");

    const floor = screen.getByTestId("bn-v2-nav-row-floor");
    expect(floor.querySelector('[role="switch"], input[type="checkbox"]')).toBeNull();

    const nielsen = screen.getByTestId("bn-v2-nav-row-nielsen");
    expect(
      nielsen.querySelector('[role="switch"], input[type="checkbox"]'),
    ).not.toBeNull();
  });

  it("toggling does not also select the row", async () => {
    // The switch is a control ON a navigation row; a click that both enabled a
    // codebook and navigated to it would make one gesture do two things.
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-sentiment");

    const sw = screen
      .getByTestId("bn-v2-nav-row-sentiment")
      .querySelector('[role="switch"], input[type="checkbox"]')!;
    fireEvent.click(sw);

    await waitFor(() => {
      const api = screen.getByTestId("bn-v2-nav-row-sentiment");
      expect(api.className).not.toContain("active");
    });
  });

  it("hides the switch in an exported report", async () => {
    // Read-only and offline: `/framework-states` is a write.
    const exportData = await import("../utils/exportData");
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-nielsen");
    expect(
      screen
        .getByTestId("bn-v2-nav-row-nielsen")
        .querySelector('[role="switch"], input[type="checkbox"]'),
    ).toBeNull();
    vi.mocked(exportData.isExportMode).mockRestore();
  });
});

describe("Browse Library closes the rail's one gap", () => {
  // The rail is installed-only (D17), so a codebook the researcher has not
  // taken appears nowhere in it. v1 listed those as greyed rows, each its own
  // door to the catalogue; v2 removed the rows, which removed the doors with
  // them. This button is the replacement.

  it("sits after the last framework row", async () => {
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-nielsen");
    const nav = screen.getByTestId("bn-v2-nav");
    const kids = Array.from(nav.children);
    expect(kids.indexOf(screen.getByTestId("bn-v2-nav-browse"))).toBe(kids.length - 1);
    // "Browse Codebooks", not "Browse Library": the label changed when the lens
    // graduated on 31 Aug 2026, so the button could take `menu.codes.browseCodebooks`'s
    // existing translations in 21 locales instead of seeding new ones — and it
    // now matches the native menu item word for word.
    expect(screen.getByTestId("bn-v2-nav-browse")).toHaveTextContent("Browse Codebooks");
  });

  it("is the house small secondary, not a sidebar dialect of one", async () => {
    // The same classes as the codebook page's Review button. This shipped
    // first as `.sidebar-mini-btn` — v1's atom with its padding retuned to
    // fit — which is a bespoke control wearing a house class.
    renderSidebar();
    const btn = await screen.findByTestId("bn-v2-nav-browse");
    expect(btn.className).toBe("bn-btn bn-btn-secondary bn-btn-sm");
  });

  it("sits inside `.v2-nav`, which is what puts `bn-btn-sm` in scope", async () => {
    // `.bn-btn-sm` is scoped to `.v2-layout` / `.section-heading` on purpose —
    // the size axis is a declared gap, not a promoted atom. The navigator is
    // in the left panel, inside neither, so without this class the button
    // silently falls back to full `.bn-btn` metrics: no error, just the wrong
    // size. Deleting the class would leave every test above still green.
    const { container } = renderSidebar();
    const btn = await screen.findByTestId("bn-v2-nav-browse");
    expect(container.querySelector("nav.v2-nav")).not.toBeNull();
    expect(btn.closest(".v2-nav")).not.toBeNull();
  });

  it("goes where the lens's own Browse Library goes — `?view=library`", async () => {
    // Same destination, same mechanism. If this ever diverges from
    // `CodebookV2`'s `setView("browse")`, one of the two buttons is lying —
    // and the lens reads the param, so a wrong value is a button that does
    // nothing rather than one that errors.
    renderSidebar("/report/codebook-v2?keep=1");
    fireEvent.click(await screen.findByTestId("bn-v2-nav-browse"));
    await waitFor(() => {
      const q = new URLSearchParams(screen.getByTestId("loc-search").textContent ?? "");
      expect(q.get("view")).toBe("library");
      // Other params survive: the handler edits a copy of `prev` rather than
      // replacing the query wholesale.
      expect(q.get("keep")).toBe("1");
    });
  });

  it("is absent from an exported report (Q14)", async () => {
    // The templates route is SERVER_ONLY and installing is a write, so there is
    // no catalogue to browse — the same reason the lens hides its own button.
    const exportData = await import("../utils/exportData");
    vi.spyOn(exportData, "isExportMode").mockReturnValue(true);
    renderSidebar();
    await screen.findByTestId("bn-v2-nav-row-nielsen");
    expect(screen.queryByTestId("bn-v2-nav-browse")).toBeNull();
    vi.mocked(exportData.isExportMode).mockRestore();
  });
});

// ── The rows themselves ────────────────────────────────────────────────────

describe("buildBooks", () => {
  const build = (
    tpl: TemplateListResponse | null = templates,
    states: Record<string, boolean> = {},
  ) => buildBooks(codebook, tpl, states, "Ikea");

  const byId = (rows: V2NavBook[], id: string) => rows.find((r) => r.id === id)!;

  it("names the floor after the project", () => {
    expect(byId(build(), "").title).toBe("Ikea tags");
  });

  it("lists only what is installed (D17)", () => {
    // cliux is in the catalogue and not in this project's groups.
    expect(build().map((r) => r.id).sort()).toEqual(["", "nielsen", "sentiment"]);
  });

  it("derives built-in from an ABSENT AUTHOR, never an id list", () => {
    // A hardcoded list files the next built-in under Frameworks silently, and
    // nothing fails.
    expect(byId(build(), "sentiment").builtIn).toBe(true);
    expect(byId(build(), "nielsen").builtIn).toBe(false);
  });

  it("carries the system fact in the DATA, for the page to render (D23)", () => {
    expect(byId(build(), "nielsen").provenance).toBe("Jakob Nielsen");
    expect(byId(build(), "nielsen").provenanceIsPerson).toBe(true);
    expect(byId(build(), "sentiment").provenance).toBe("On by default");
    expect(byId(build(), "sentiment").provenanceIsPerson).toBe(false);
  });

  it("sums tentative counts into the pending badge (D10)", () => {
    expect(byId(build(), "nielsen").pending).toBe(5);
    expect(byId(build(), "sentiment").pending).toBe(2);
  });

  it("treats an absent framework-state entry as enabled", () => {
    // The wire omits a framework the researcher has never touched; absent must
    // not read as off, or a fresh install would arrive switched off.
    expect(byId(build(templates, {}), "nielsen").enabled).toBe(true);
    expect(byId(build(templates, { nielsen: false }), "nielsen").enabled).toBe(false);
  });

  it("still lists installed codebooks when the catalogue is unavailable", () => {
    // Q14: `/codebook/templates` is SERVER_ONLY, so it is absent from an
    // export. Driving the rows off the CODEBOOK rather than the template list
    // means the reader can still navigate — with ids for titles, which is
    // worse than names and far better than an empty navigator.
    const rows = build(null);
    expect(rows.map((r) => r.id).sort()).toEqual(["", "nielsen", "sentiment"]);
    expect(byId(rows, "nielsen").title).toBe("nielsen");
  });
});
