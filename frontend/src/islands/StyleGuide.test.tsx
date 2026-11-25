import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { FocusProvider } from "../contexts/FocusContext";
import { resetSignalWorkingStore, setSignalWorkingOpen } from "../contexts/SignalWorkingStore";
import { StyleGuide } from "./StyleGuide";
import { sectionId, storiesOf } from "./styleGuide/csf";
import { SECTIONS } from "./styleGuide/sections";

const root = () => document.documentElement;

function renderAt(url = "/report/style-guide") {
  return render(
    <MemoryRouter initialEntries={[url]}>
      {/* AppLayout provides the focus store in the app; the quote cards read it. */}
      <FocusProvider>
        <StyleGuide />
      </FocusProvider>
    </MemoryRouter>,
  );
}

describe("StyleGuide", () => {
  let style: HTMLStyleElement;

  beforeEach(() => {
    // A stand-in theme sheet: the foundations read tokens from whatever CSS is loaded.
    style = document.createElement("style");
    style.textContent =
      ":root { --bn-colour-bg: #ffffff; --bn-colour-text: #111111; --bn-text-body: 15px; --bn-text-body-lh: 1.5;" +
      " --bn-weight-normal: 420; --bn-space-md: 0.75rem; --bn-radius-md: 6px; --bn-sentiment-delight: #0a0; }";
    document.head.appendChild(style);
  });

  afterEach(() => {
    style.remove();
    for (const a of ["data-color-theme", "data-theme", "data-platform"]) root().removeAttribute(a);
    root().style.colorScheme = "";
  });

  it("renders every section and every story it lists, with nothing caught by a boundary", () => {
    renderAt();
    for (const mod of SECTIONS) {
      const id = sectionId(mod.default);
      expect(screen.getByTestId(`bn-sg-section-${id}`)).toBeTruthy();
      for (const { key } of storiesOf(mod)) {
        expect(screen.getByTestId(`bn-sg-story-${id}-${key}`)).toBeTruthy();
      }
    }
    expect(document.querySelector(".bn-route-error")).toBeNull();
  });

  it("draws the foundations from the loaded CSS, not a list of its own", () => {
    renderAt();
    expect(screen.getByTestId("bn-sg-type---bn-text-body")).toBeTruthy();
    expect(screen.queryByTestId("bn-sg-type---bn-text-body-lh")).toBeNull();
    expect(screen.getByTestId("bn-sg-colour---bn-colour-bg")).toBeTruthy();
    expect(screen.getByTestId("bn-sg-colour---bn-sentiment-delight")).toBeTruthy();
    expect(screen.getByTestId("bn-sg-space---bn-space-md")).toBeTruthy();
    expect(screen.getByTestId("bn-sg-radius---bn-radius-md")).toBeTruthy();
  });

  it("draws the atoms with the shipped components", () => {
    renderAt();
    expect(document.querySelectorAll(".bn-person-badge").length).toBeGreaterThanOrEqual(10);
    expect(document.querySelector(".toolbar-btn-toggle.active")).not.toBeNull();
    for (const status of ["running", "completed", "partial", "failed", "cancelled"]) {
      expect(screen.getByTestId(`bn-sg-chip-${status}`).querySelector(".activity-chip")).not.toBeNull();
    }
    expect(document.querySelector(".bn-seg")).not.toBeNull();
    expect(document.querySelector(".bn-sparkline")).not.toBeNull();
    // The confirmation cards wait for a click (each takes focus on mount), then draw inline.
    expect(document.querySelector(".confirm-dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Show the confirmation cards" }));
    expect(document.querySelectorAll(".confirm-dialog")).toHaveLength(4);
  });

  it("draws the quote card in its states, focus and selection through the app's focus store", () => {
    const { unmount } = renderAt();
    const card = (id: string) => document.getElementById(id) as HTMLElement;
    expect(document.querySelectorAll(".quote-group .quote-card").length).toBeGreaterThanOrEqual(9);
    expect(card("q-sg-starred").classList.contains("starred")).toBe(true);
    expect(card("q-sg-focused").classList.contains("bn-focused")).toBe(true);
    expect(card("q-sg-selected-1").classList.contains("bn-selected")).toBe(true);
    expect(card("q-sg-selected-2").classList.contains("bn-selected")).toBe(true);
    expect(card("q-sg-rest-1").classList.contains("bn-focused")).toBe(false);
    expect(card("q-sg-search").querySelector("mark")?.textContent?.toLowerCase()).toBe("delivery");
    expect(card("q-sg-restore").querySelector(".badge-restore")).not.toBeNull();
    unmount();
  });

  it("draws the organisms from their prop-driven parts, counted by the app's own rules", () => {
    renderAt();
    expect(document.querySelector(".toolbar .toolbar-btn")).not.toBeNull();
    expect(document.querySelectorAll(".signal-cards .signal-card")).toHaveLength(2);
    expect(document.querySelectorAll(".signal-card.bn-selected")).toHaveLength(1);
    // The metrics (Metric rows) show while the chart is open: the reader's preference, off by default.
    expect(document.querySelector(".signal-card .signal-card-metrics")).toBeNull();
    act(() => setSignalWorkingOpen(true));
    expect(document.querySelectorAll(".signal-card .signal-card-metrics .metric-value").length).toBeGreaterThan(0);
    act(() => resetSignalWorkingStore());
    expect(document.querySelector(".threshold-body .threshold-slider .threshold-histogram")).not.toBeNull();
    // Fixture confidences at the default lines (0.30, 0.70): 7 below, 16 between, 17 at or above.
    const counts = Array.from(document.querySelectorAll(".threshold-zone-counter-count")).map((n) => n.textContent);
    expect(counts.join(" ")).toMatch(/7/);
    expect(counts.join(" ")).toMatch(/17/);
    expect(document.querySelectorAll(".bn-journey-sep").length).toBeGreaterThan(0);
    // The dialog opens through the shell, over the page.
    expect(screen.queryByRole("dialog", { name: "Export the report" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Open the dialog" }));
    expect(screen.getByRole("dialog", { name: "Export the report" })).toBeTruthy();
  });

  it("draws the session timeline in the grid's slice and the transcript's, with the diagnostics", async () => {
    renderAt();
    // Lazy, as in the app: wait for the chunks.
    const slice = (await screen.findByTestId("bn-sg-story-organisms-session-timeline-GridSlice")).querySelector(".bn-tapestry");
    await vi.waitFor(() => expect(slice?.querySelector(".bn-tapestry-scroll .bn-tapestry-svg")).not.toBeNull());
    const svg = slice!.querySelector(".bn-tapestry-svg")!;
    expect(svg.querySelectorAll(".bn-tp-lane")).toHaveLength(5);
    expect(svg.querySelectorAll(".bn-tp-flag")).toHaveLength(7);
    expect(svg.querySelectorAll(".bn-tp-bar")).toHaveLength(14);
    await vi.waitFor(() => expect(slice!.querySelector(".bn-tapestry-scroll > .bn-dx")).not.toBeNull());
    expect(slice!.querySelector(".bn-dx-headline")?.textContent).toBe(
      "8% of windows retried · 00:10 with sound but no words · 2 inaudible (00:05)",
    );

    const timelines = Array.from(document.querySelectorAll(".bn-transcript-timeline"));
    expect(timelines).toHaveLength(3);
    await vi.waitFor(() => expect(timelines.every((t) => t.querySelector(".bn-tapestry-svg"))).toBe(true));
    const laneCounts = timelines.map((t) => t.querySelectorAll(".bn-tp-lane").length);
    expect(laneCounts[0]).toBeLessThan(laneCounts[1]);
    expect(laneCounts[1]).toBeLessThan(laneCounts[2]);
    for (const t of timelines) {
      expect(t.querySelector(".bn-tp-window")).not.toBeNull();
      expect(t.querySelector(".bn-tp-player")).not.toBeNull();
    }

    const diag = await screen.findByTestId("bn-sg-story-organisms-session-timeline-Diagnostics");
    await vi.waitFor(() => expect(diag.querySelectorAll(".bn-dx")).toHaveLength(2));
    expect(diag.querySelector(".bn-dx-headline")?.textContent).toBe("Left for Whisper: low confidence under en-GB");
  });

  it("sets the theme through the app's own functions and puts it back on leaving", async () => {
    root().setAttribute("data-color-theme", "default");
    const { unmount } = renderAt("/report/style-guide?palette=edo&appearance=dark&platform=desktop");
    expect(root().getAttribute("data-color-theme")).toBe("edo");
    expect(root().getAttribute("data-theme")).toBe("dark");
    expect(root().style.colorScheme).toBe("dark");
    expect(root().getAttribute("data-platform")).toBe("desktop");
    // Settings' General section applies the SAVED appearance when its lazy chunk
    // lands, after this page set its own; the page puts its theme back.
    root().removeAttribute("data-theme");
    await new Promise((r) => setTimeout(r, 0));
    expect(root().getAttribute("data-theme")).toBe("dark");
    unmount();
    expect(root().getAttribute("data-color-theme")).toBe("default");
    expect(root().hasAttribute("data-theme")).toBe(false);
    expect(root().hasAttribute("data-platform")).toBe(false);
  });

  it("ignores a palette the app does not know", () => {
    root().setAttribute("data-color-theme", "default");
    renderAt("/report/style-guide?palette=nonsense");
    expect(root().getAttribute("data-color-theme")).toBe("default");
  });

  it("the matrix is four documents of this route, one per house theme", () => {
    renderAt("/report/style-guide?view=matrix&section=atoms-buttons");
    const srcs = Array.from(document.querySelectorAll(".bn-sg-matrix iframe")).map((f) => f.getAttribute("src"));
    expect(srcs).toHaveLength(4);
    for (const s of srcs) {
      const q = new URLSearchParams(s!.split("?")[1]);
      expect(q.get("frame")).toBe("1");
      expect(q.get("section")).toBe("atoms-buttons");
    }
    expect(srcs.map((s) => new URLSearchParams(s!.split("?")[1]).get("palette") + "/" + new URLSearchParams(s!.split("?")[1]).get("appearance"))).toEqual([
      "default/light",
      "default/dark",
      "edo/light",
      "edo/dark",
    ]);
  });

  it("a frame draws only its section, scrolled to the top of the frame", () => {
    const scrolled: Element[] = [];
    // jsdom has no scrollIntoView; record what the frame scrolls to.
    Element.prototype.scrollIntoView = function (this: Element) {
      scrolled.push(this);
    };
    renderAt("/report/style-guide?frame=1&section=atoms-buttons");
    expect(scrolled.map((el) => el.id)).toEqual(["atoms-buttons"]);
    expect(screen.getByTestId("bn-sg-section-atoms-buttons")).toBeTruthy();
    expect(document.querySelectorAll(".bn-sg-section")).toHaveLength(1);
    expect(document.querySelector(".bn-sg-controls")).toBeNull();
    delete (Element.prototype as { scrollIntoView?: unknown }).scrollIntoView;
  });

  it("each section module is valid CSF: its order lists exactly its stories", () => {
    for (const mod of SECTIONS) {
      const named = Object.keys(mod).filter((k) => k !== "default" && k !== "__namedExportsOrder");
      expect([...mod.__namedExportsOrder].sort()).toEqual(named.sort());
    }
  });
});
