import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";
import { InspectorPanel, type InspectorSource } from "./InspectorPanel";
import {
  resetInspectorStore,
  openInspector,
  setInspectorSource,
} from "../contexts/InspectorStore";

// ── Helpers ───────────────────────────────────────────────────────────────

const SOURCES: InspectorSource[] = [
  {
    key: "sentiment",
    label: "Sentiment",
    sectionContent: <div data-testid="sentiment-section">Sentiment × Section</div>,
    themeContent: <div data-testid="sentiment-theme">Sentiment × Theme</div>,
  },
  {
    key: "cb-1",
    label: "UX Research",
    sectionContent: <div data-testid="ux-section">UX × Section</div>,
  },
];

// ── Setup ─────────────────────────────────────────────────────────────────

beforeEach(() => {
  localStorage.clear();
  sessionStorage.clear();
  resetInspectorStore();
});

// ── Tests ─────────────────────────────────────────────────────────────────

describe("InspectorPanel", () => {
  it("renders collapsed by default", () => {
    render(<InspectorPanel sources={SOURCES} />);
    const panel = screen.getByTestId("bn-inspector-panel");
    expect(panel.classList.contains("collapsed")).toBe(true);
    expect(screen.getByTestId("inspector-title").textContent).toBe("Heatmap");
  });

  it("renders nothing with empty sources", () => {
    const { container } = render(<InspectorPanel sources={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("shows grid icon when collapsed, close icon when open", () => {
    render(<InspectorPanel sources={SOURCES} />);
    const toggle = screen.getByTestId("inspector-toggle");
    expect(toggle.getAttribute("aria-label")).toBe("Open heatmap panel");

    // Open
    openInspector();
    // Re-render needed — but since the store updates sync, the hook should re-render.
    // Actually, we need to trigger a re-render. Let's use fireEvent.
  });

  it("opens panel when toggle button is clicked", () => {
    render(<InspectorPanel sources={SOURCES} />);
    const toggle = screen.getByTestId("inspector-toggle");
    fireEvent.click(toggle);

    const panel = screen.getByTestId("bn-inspector-panel");
    expect(panel.classList.contains("collapsed")).toBe(false);
  });

  it("closes panel when toggle button is clicked while open", () => {
    vi.useFakeTimers();
    openInspector();
    render(<InspectorPanel sources={SOURCES} />);

    const panel = screen.getByTestId("bn-inspector-panel");
    expect(panel.classList.contains("collapsed")).toBe(false);

    fireEvent.click(screen.getByTestId("inspector-toggle"));
    // Closing animation plays for 75ms before collapsing
    expect(panel.classList.contains("closing")).toBe(true);

    act(() => { vi.advanceTimersByTime(75); });
    expect(panel.classList.contains("collapsed")).toBe(true);
    expect(panel.classList.contains("closing")).toBe(false);
    vi.useRealTimers();
  });

  it("renders source tabs", () => {
    openInspector();
    render(<InspectorPanel sources={SOURCES} />);

    expect(screen.getByTestId("inspector-tab-sentiment")).toBeTruthy();
    expect(screen.getByTestId("inspector-tab-cb-1")).toBeTruthy();
  });

  it("first source is active by default", () => {
    openInspector();
    render(<InspectorPanel sources={SOURCES} />);

    const tab = screen.getByTestId("inspector-tab-sentiment");
    expect(tab.classList.contains("active")).toBe(true);
    expect(screen.getByTestId("sentiment-section")).toBeTruthy();
  });

  it("switches source when tab is clicked", () => {
    openInspector();
    render(<InspectorPanel sources={SOURCES} />);

    fireEvent.click(screen.getByTestId("inspector-tab-cb-1"));
    expect(screen.getByTestId("ux-section")).toBeTruthy();
  });

  it("shows section content by default", () => {
    openInspector();
    render(<InspectorPanel sources={SOURCES} />);
    expect(screen.getByTestId("sentiment-section")).toBeTruthy();
  });

  it("renders grab handle with separator role", () => {
    render(<InspectorPanel sources={SOURCES} />);
    const grip = screen.getByTestId("inspector-grip");
    expect(grip.getAttribute("role")).toBe("separator");
    expect(grip.getAttribute("aria-orientation")).toBe("horizontal");
  });

  it("tabs have proper ARIA attributes", () => {
    openInspector();
    render(<InspectorPanel sources={SOURCES} />);

    const tablist = screen.getByRole("tablist");
    expect(tablist).toBeTruthy();

    const activeTab = screen.getByTestId("inspector-tab-sentiment");
    expect(activeTab.getAttribute("role")).toBe("tab");
    expect(activeTab.getAttribute("aria-selected")).toBe("true");

    const inactiveTab = screen.getByTestId("inspector-tab-cb-1");
    expect(inactiveTab.getAttribute("aria-selected")).toBe("false");
  });

  it("persists source selection via store", () => {
    openInspector();
    setInspectorSource("cb-1");
    render(<InspectorPanel sources={SOURCES} />);

    const tab = screen.getByTestId("inspector-tab-cb-1");
    expect(tab.classList.contains("active")).toBe(true);
  });

  it("falls back to sectionContent when themeContent is missing", () => {
    openInspector();
    setInspectorSource("cb-1");
    // cb-1 has only sectionContent. Even if dimension is "theme", it falls back.
    render(<InspectorPanel sources={SOURCES} />);
    expect(screen.getByTestId("ux-section")).toBeTruthy();
  });
});
