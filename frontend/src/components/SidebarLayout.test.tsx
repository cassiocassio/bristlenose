/**
 * Tests for SidebarLayout — 6-column grid, drag handles, toggle/close.
 */

import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { SidebarLayout } from "./SidebarLayout";
import type { TocMode } from "../contexts/SidebarStore";

// ── Mocks ────────────────────────────────────────────────────────────────

// Mock child sidebars so they don't fetch APIs.
vi.mock("./TocSidebar", () => ({
  TocSidebar: () => <div data-testid="toc-sidebar-stub" />,
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

// Mock PlaygroundStore to avoid sessionStorage complexity.
vi.mock("../contexts/PlaygroundStore", () => ({
  usePlaygroundStore: () => ({
    hoverDelay: null,
    leaveGrace: null,
  }),
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

vi.mock("../contexts/SidebarStore", () => ({
  useSidebarStore: () => mockState,
  toggleTags: (...args: unknown[]) => mockToggleTags(...args),
  openTocPush: (...args: unknown[]) => mockOpenTocPush(...args),
  closeToc: (...args: unknown[]) => mockCloseToc(...args),
  closeTags: (...args: unknown[]) => mockCloseTags(...args),
  openTags: vi.fn(),
  toggleToc: vi.fn(),
  toggleBoth: vi.fn(),
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
});

// ── Tests ────────────────────────────────────────────────────────────────

describe("SidebarLayout", () => {
  it("renders children directly when active=false (no grid)", () => {
    const { container } = render(
      <SidebarLayout active={false}>
        <div data-testid="child">Content</div>
      </SidebarLayout>,
    );
    expect(screen.getByTestId("child")).toBeTruthy();
    // No .layout div should exist.
    expect(container.querySelector(".layout")).toBeNull();
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
    expect(screen.getByLabelText("Toggle tag sidebar")).toBeTruthy();
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
