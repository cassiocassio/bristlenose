/**
 * Tests for SidebarLayout — 6-column grid, drag handles, toggle/close.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SidebarLayout } from "./SidebarLayout";
import { useTocShowing } from "../contexts/TocShowing";
import type { TocMode } from "../contexts/SidebarStore";

// ── Mocks ────────────────────────────────────────────────────────────────

// Mock child sidebars so they don't fetch APIs.
vi.mock("./TocSidebar", () => ({
  TocSidebar: (props: Record<string, unknown>) => (
    <div data-testid="toc-sidebar-stub" data-has-overlay-close={!!props.onOverlayClose} />
  ),
}));
vi.mock("./TagSidebar", () => ({
  TagSidebar: () => <div data-testid="tag-sidebar-stub" />,
}));
vi.mock("./Minimap", () => ({
  Minimap: () => <div className="minimap-slot" data-testid="minimap-stub" />,
}));

// Mock useDragResize to avoid pointer event complexity in layout tests.
const mockHandlePointerDown = vi.fn();
const mockHandleKeyDown = vi.fn();
vi.mock("../hooks/useDragResize", () => ({
  useDragResize: () => ({
    handlePointerDown: mockHandlePointerDown,
    handleKeyDown: mockHandleKeyDown,
    isDragging: false,
  }),
  MIN_WIDTH: 200,
  MAX_WIDTH: 320,
}));

// Mock useTocOverlay to avoid hover/timer complexity in layout tests.
vi.mock("../hooks/useTocOverlay", () => ({
  useTocOverlay: () => ({
    onRailMouseEnter: vi.fn(),
    onRailMouseLeave: vi.fn(),
    onPanelMouseEnter: vi.fn(),
    onPanelMouseLeave: vi.fn(),
    onRailAreaClick: vi.fn(),
    onButtonMouseEnter: vi.fn(),
    onButtonMouseLeave: vi.fn(),
  }),
}));

// Mock the playground's sidebar tuning to drive overlay variants directly.
let mockPlayground = { hoverDelay: null, leaveGrace: null, overlayStyle: null as string | null };
vi.mock("../contexts/sidebarTuning", () => ({
  useSidebarTuning: () => mockPlayground,
}));

// Mock embedded detection — default false (browser); flip per-test.
let mockEmbedded = false;
vi.mock("../utils/embedded", () => ({
  isEmbedded: () => mockEmbedded,
}));

// Mock SidebarStore — we control state via mockState.
const mockOpenTocPush = vi.fn();
const mockToggleTags = vi.fn();
const mockCloseToc = vi.fn();
const mockCloseTags = vi.fn();

let mockState: {
  tocMode: TocMode;
  tagsOpen: boolean;
  tocWidth: number;
  tagsWidth: number;
  hiddenTagGroups: Set<string>;
} = {
  tocMode: "closed",
  tagsOpen: false,
  tocWidth: 280,
  tagsWidth: 280,
  hiddenTagGroups: new Set<string>(),
};

vi.mock("../contexts/SidebarStore", async (importOriginal) => ({
  // The fit is real: these tests set widths and open flags and expect the
  // grid classes that follow, and an unmeasured width (no availableWidth on
  // mockState) fits everything — see "an unmeasured width closes nothing".
  fitPanels: (await importOriginal<typeof import("../contexts/SidebarStore")>()).fitPanels,
  navBarNeeds: (await importOriginal<typeof import("../contexts/SidebarStore")>()).navBarNeeds,
  setLayoutContext: vi.fn(),
  useSidebarStore: () => mockState,
  toggleTags: (...args: unknown[]) => mockToggleTags(...args),
  openTocPush: (...args: unknown[]) => mockOpenTocPush(...args),
  closeToc: (...args: unknown[]) => mockCloseToc(...args),
  closeTags: (...args: unknown[]) => mockCloseTags(...args),
  openTags: vi.fn(),
  toggleToc: vi.fn(),
  toggleBoth: vi.fn(),
  hideAllSidebars: vi.fn(),
  showAllSidebars: vi.fn(),
  openTocOverlay: vi.fn(),
}));

// ── Setup ────────────────────────────────────────────────────────────────

beforeEach(() => {
  vi.clearAllMocks();
  mockState = {
    tocMode: "closed",
    tagsOpen: false,
    tocWidth: 280,
    tagsWidth: 280,
    hiddenTagGroups: new Set(),
  };
  mockPlayground = { hoverDelay: null, leaveGrace: null, overlayStyle: null };
  mockEmbedded = false;
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("SidebarLayout", () => {
  it("renders inert rail layout when active=false", () => {
    const { container } = render(
      <SidebarLayout active={false}>
        <div data-testid="child">Content</div>
      </SidebarLayout>,
    );
    expect(screen.getByTestId("child")).toBeTruthy();
    // Inert 2-column layout with cosmetic rail.
    const layout = container.querySelector(".layout.layout-inert");
    expect(layout).toBeTruthy();
    expect(container.querySelector(".toc-rail.toc-rail-inert")).toBeTruthy();
    // No full sidebar elements (no drag handles, no tag rail).
    expect(container.querySelector(".tag-rail")).toBeNull();
    expect(container.querySelector(".drag-handle")).toBeNull();
  });

  it("puts a lens's own rail content in the inert rail (the Discussion guide button)", () => {
    const { container } = render(
      <SidebarLayout active={false} inertRail={<button className="rail-btn">guide</button>}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-rail.toc-rail-inert .rail-btn")?.textContent).toBe("guide");
  });

  it("renders 6-column grid structure when active=true", () => {
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout")).toBeTruthy();
    expect(container.querySelector(".toc-rail")).toBeTruthy();
    expect(container.querySelector(".toc-sidebar")).toBeTruthy();
    expect(container.querySelector(".center")).toBeTruthy();
    expect(container.querySelector(".tag-sidebar")).toBeTruthy();
    expect(container.querySelector(".tag-rail")).toBeTruthy();
    expect(container.querySelector(".minimap-slot")).toBeTruthy();
  });

  it("TOC rail button has correct aria-label", () => {
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(screen.getByLabelText("Toggle table of contents")).toBeTruthy();
  });

  it("Tag rail button has correct aria-label", () => {
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(screen.getAllByLabelText("Tags").length).toBeGreaterThan(0);
  });

  it("adds .toc-open class when tocMode is push", () => {
    mockState = { ...mockState, tocMode: "push" };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout.toc-open")).toBeTruthy();
  });

  it("adds .toc-overlay class when tocMode is overlay", () => {
    mockState = { ...mockState, tocMode: "overlay" };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout.toc-overlay")).toBeTruthy();
    // Rail should stay visible in overlay mode (no .toc-open class)
    expect(container.querySelector(".layout.toc-open")).toBeNull();
  });

  it("adds .tags-open class when tagsOpen is true", () => {
    mockState = { ...mockState, tagsOpen: true };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout.tags-open")).toBeTruthy();
  });

  it("sets --toc-width inline style when tocMode is push", () => {
    mockState = { ...mockState, tocMode: "push", tocWidth: 350 };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    const layout = container.querySelector(".layout") as HTMLElement;
    expect(layout.style.getPropertyValue("--toc-width")).toBe("350px");
  });

  it("sets --toc-width inline style when tocMode is overlay", () => {
    mockState = { ...mockState, tocMode: "overlay", tocWidth: 300 };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    const layout = container.querySelector(".layout") as HTMLElement;
    expect(layout.style.getPropertyValue("--toc-width")).toBe("300px");
  });

  it("sets --tags-width inline style when tagsOpen", () => {
    mockState = { ...mockState, tagsOpen: true, tagsWidth: 400 };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    const layout = container.querySelector(".layout") as HTMLElement;
    expect(layout.style.getPropertyValue("--tags-width")).toBe("400px");
  });

  it("does not set --toc-width when tocMode is closed", () => {
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    const layout = container.querySelector(".layout") as HTMLElement;
    expect(layout.style.getPropertyValue("--toc-width")).toBe("");
  });
});

describe("drag handles — conditional rendering", () => {
  it("renders tag rail drag handle when sidebar is closed", () => {
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".tag-rail-drag")).toBeTruthy();
    expect(container.querySelector(".tag-drag-handle")).toBeNull();
  });

  it("renders sidebar drag handles when sidebars are open in push mode", () => {
    mockState = { ...mockState, tocMode: "push", tagsOpen: true };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-drag-handle")).toBeTruthy();
    expect(container.querySelector(".tag-drag-handle")).toBeTruthy();
    expect(container.querySelector(".tag-rail-drag")).toBeNull();
  });

  it("renders toc drag handle in overlay mode", () => {
    mockState = { ...mockState, tocMode: "overlay" };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-drag-handle")).toBeTruthy();
  });
});

describe("button interactions", () => {
  it("TOC rail button click fires (via withAnimation)", () => {
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    fireEvent.click(screen.getByLabelText("Toggle table of contents"));
    // withAnimation wraps openTocPush in rAF — the mock is called via rAF.
  });

  it("close button exists when TOC sidebar is in push mode", () => {
    mockState = { ...mockState, tocMode: "push" };
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(screen.getByLabelText("Close table of contents")).toBeTruthy();
  });

  it("close button exists when tag sidebar is open", () => {
    mockState = { ...mockState, tagsOpen: true };
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(screen.getByLabelText("Close tag sidebar")).toBeTruthy();
  });
});

describe("overlay animation", () => {
  it("adds toc-closing class when close button clicked in overlay mode", () => {
    mockState = { ...mockState, tocMode: "overlay" };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    fireEvent.click(screen.getByLabelText("Close table of contents"));
    expect(container.querySelector(".layout.toc-closing")).toBeTruthy();
  });

  it("adds overlay-ios class when playground overlayStyle is ios", () => {
    mockState = { ...mockState, tocMode: "overlay" };
    mockPlayground = { ...mockPlayground, overlayStyle: "ios" };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout.toc-overlay.overlay-ios")).toBeTruthy();
  });

  it("does not add overlay-ios class when playground overlayStyle is null", () => {
    mockState = { ...mockState, tocMode: "overlay" };
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout.overlay-ios")).toBeNull();
  });

  it("passes onOverlayClose to TocSidebar", () => {
    mockState = { ...mockState, tocMode: "overlay" };
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    const stub = screen.getByTestId("toc-sidebar-stub");
    expect(stub.getAttribute("data-has-overlay-close")).toBe("true");
  });
});

describe("embedded mode (macOS desktop)", () => {
  it("adds .embedded class to the active grid", () => {
    mockEmbedded = true;
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout.embedded")).toBeTruthy();
  });

  it("adds .embedded class to the inert layout (active=false)", () => {
    mockEmbedded = true;
    const { container } = render(
      <SidebarLayout active={false}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".layout.layout-inert.embedded")).toBeTruthy();
  });

  it("hides the TOC close-× when the sidebar is open in push mode", () => {
    mockEmbedded = true;
    mockState = { ...mockState, tocMode: "push" };
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(screen.queryByLabelText("Close table of contents")).toBeNull();
  });

  it("hides the tag close-× when the tag sidebar is open", () => {
    mockEmbedded = true;
    mockState = { ...mockState, tagsOpen: true };
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(screen.queryByLabelText("Close tag sidebar")).toBeNull();
  });

  it("makes the center region programmatically focusable (tabIndex -1)", () => {
    mockEmbedded = true;
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    const center = container.querySelector(".center") as HTMLElement;
    expect(center.getAttribute("tabindex")).toBe("-1");
  });

  it("keeps both close-× buttons in the browser (not embedded)", () => {
    mockEmbedded = false;
    mockState = { ...mockState, tocMode: "push", tagsOpen: true };
    render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(screen.getByLabelText("Close table of contents")).toBeTruthy();
    expect(screen.getByLabelText("Close tag sidebar")).toBeTruthy();
  });
});

// The header holds two things: the title (Sessions/Analysis pass one, Quotes
// and Codebooks no longer do) and the close ×, which embedded mode gates out.
// Embedded + no title leaves it holding neither — so it must not render at all,
// or it sits at the top of the panel as an empty padded box pushing the first
// heading off the datum the toolbar establishes. jsdom can't measure that box
// (every rect is zero), so these assert the element's existence, which is the
// thing the padding hangs off.
describe("left sidebar header — renders only when it holds something", () => {
  beforeEach(() => {
    mockState = { ...mockState, tocMode: "push" };
  });

  it("is absent in embedded mode when no title is passed", () => {
    mockEmbedded = true;
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-sidebar-header")).toBeNull();
  });

  it("is present in embedded mode when a title is passed", () => {
    mockEmbedded = true;
    const { container } = render(
      <SidebarLayout active={true} leftPanelTitle="Sessions">
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-sidebar-header")).toBeTruthy();
    expect(screen.getByText("Sessions")).toBeTruthy();
  });

  it("survives in the browser without a title — the close × keeps it alive", () => {
    mockEmbedded = false;
    const { container } = render(
      <SidebarLayout active={true}>
        <div>Content</div>
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-sidebar-header")).toBeTruthy();
    expect(screen.getByLabelText("Close table of contents")).toBeTruthy();
  });

  it("renders no title element when none is passed, on either surface", () => {
    for (const embedded of [true, false]) {
      mockEmbedded = embedded;
      const { container, unmount } = render(
        <SidebarLayout active={true}>
          <div>Content</div>
        </SidebarLayout>,
      );
      // Scoped to .toc-sidebar — the tag sidebar has its own always-titled
      // header ("Tags") and an unscoped query would match that instead.
      // Guards the old `leftPanelTitle ?? t("quotes.contents")` fallback from
      // creeping back in — it would render "Contents" here.
      expect(container.querySelector(".toc-sidebar .sidebar-title")).toBeNull();
      unmount();
    }
  });
});

describe("the left panel's header control (the Quotes lens's grouping)", () => {
  // SidebarLayout is the one owner of "is the sidebar showing": it draws the
  // control in its header only then, and tells the page through context so
  // the page can take it back. Both read the same fit, so the control is in
  // exactly one place.
  function Probe() {
    return <span data-testid="probe">{String(useTocShowing())}</span>;
  }
  const header = <button data-testid="grouping">grouping</button>;

  it("sits in the sidebar header while the sidebar is a resting panel", () => {
    mockState = { ...mockState, tocMode: "push" };
    const { container } = render(
      <SidebarLayout active={true} leftPanel={<div />} leftPanelHeader={header}>
        <Probe />
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-sidebar-header [data-testid='grouping']")).toBeTruthy();
    expect(screen.getByTestId("probe")).toHaveTextContent("true");
  });

  for (const mode of ["closed", "overlay"] as const) {
    it(`stays out of the sidebar when it is ${mode}, and the page is told so`, () => {
      mockState = { ...mockState, tocMode: mode };
      render(
        <SidebarLayout active={true} leftPanel={<div />} leftPanelHeader={header}>
          <Probe />
        </SidebarLayout>,
      );
      expect(screen.queryByTestId("grouping")).toBeNull();
      expect(screen.getByTestId("probe")).toHaveTextContent("false");
    });
  }

  it("is given a header on the Mac, which otherwise draws none for an untitled panel", () => {
    mockEmbedded = true;
    mockState = { ...mockState, tocMode: "push" };
    const { container } = render(
      <SidebarLayout active={true} leftPanel={<div />} leftPanelHeader={header}>
        <div />
      </SidebarLayout>,
    );
    expect(container.querySelector(".toc-sidebar-header [data-testid='grouping']")).toBeTruthy();
  });

  it("tells a page outside an active layout that no sidebar is showing", () => {
    mockState = { ...mockState, tocMode: "push" };
    render(
      <SidebarLayout active={false} leftPanelHeader={header}>
        <Probe />
      </SidebarLayout>,
    );
    expect(screen.getByTestId("probe")).toHaveTextContent("false");
  });
});

describe("the panel just opened stays open in the grid", () => {
  // 368 floor + 240 + 280 + 80 = 968 holds both; 700 holds the floor beside
  // one panel. Without the exemption the cascade closes Contents first.
  it("keeps Contents, just opened, and closes Tags instead", () => {
    mockState = { ...mockState, tocMode: "push", tagsOpen: true, availableWidth: 700, lastOpened: "toc" } as typeof mockState;
    const { container } = render(<SidebarLayout active={true}><div /></SidebarLayout>);
    const layout = container.querySelector(".layout")!;
    expect(layout.classList.contains("toc-open")).toBe(true);
    expect(layout.classList.contains("tags-open")).toBe(false);
  });

  it("keeps Tags, just opened, and closes Contents instead", () => {
    mockState = { ...mockState, tocMode: "push", tagsOpen: true, availableWidth: 700, lastOpened: "tags" } as typeof mockState;
    const { container } = render(<SidebarLayout active={true}><div /></SidebarLayout>);
    const layout = container.querySelector(".layout")!;
    expect(layout.classList.contains("toc-open")).toBe(false);
    expect(layout.classList.contains("tags-open")).toBe(true);
  });
});

describe("the Mac's folded projects column holds the minimap back in the grid", () => {
  // 2000 holds every panel and the minimap; only the fold can hide it.
  it("hides the minimap while native reports the column folded", () => {
    mockState = { ...mockState, tocMode: "push", tagsOpen: true, availableWidth: 2000, hostColumnFolded: true } as typeof mockState;
    const { container } = render(<SidebarLayout active={true}><div /></SidebarLayout>);
    const layout = container.querySelector(".layout")!;
    expect(layout.classList.contains("minimap-hidden")).toBe(true);
    expect(layout.classList.contains("toc-open")).toBe(true);
  });

  it("shows it again once the column is back", () => {
    mockState = { ...mockState, tocMode: "push", tagsOpen: true, availableWidth: 2000, hostColumnFolded: false } as typeof mockState;
    const { container } = render(<SidebarLayout active={true}><div /></SidebarLayout>);
    expect(container.querySelector(".layout")!.classList.contains("minimap-hidden")).toBe(false);
  });
});
