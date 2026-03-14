/**
 * Tests for Tooltip — rendering, keyboard badge display,
 * platform-aware shortcut rendering.
 */

import { render, screen } from "@testing-library/react";
import { Tooltip } from "./Tooltip";
import { isMac } from "../utils/platform";

vi.mock("../utils/platform", () => ({
  isMac: vi.fn(() => true),
}));

const mockIsMac = vi.mocked(isMac);

describe("Tooltip", () => {
  it("renders children", () => {
    render(
      <Tooltip content="Search">
        <button>Click me</button>
      </Tooltip>,
    );
    expect(screen.getByRole("button", { name: "Click me" })).toBeTruthy();
  });

  it("renders tooltip text", () => {
    render(
      <Tooltip content="Search quotes">
        <button>btn</button>
      </Tooltip>,
    );
    expect(screen.getByRole("tooltip").textContent).toContain("Search quotes");
  });

  it("renders kbd badge for simple shortcut", () => {
    render(
      <Tooltip content="Search" shortcut={{ key: "/" }}>
        <button>btn</button>
      </Tooltip>,
    );
    const tooltip = screen.getByRole("tooltip");
    const kbds = tooltip.querySelectorAll("kbd");
    expect(kbds).toHaveLength(1);
    expect(kbds[0].textContent).toBe("/");
  });

  it("links trigger to tooltip via aria-describedby", () => {
    render(
      <Tooltip content="Search" shortcut={{ key: "/" }}>
        <button>btn</button>
      </Tooltip>,
    );
    const wrap = screen.getByRole("tooltip").parentElement!;
    const tooltipId = screen.getByRole("tooltip").id;
    expect(wrap.getAttribute("aria-describedby")).toBe(tooltipId);
  });

  it("wraps in .bn-tooltip-wrap span", () => {
    render(
      <Tooltip content="Test">
        <button>btn</button>
      </Tooltip>,
    );
    const wrap = screen.getByRole("tooltip").parentElement!;
    expect(wrap.classList.contains("bn-tooltip-wrap")).toBe(true);
    expect(wrap.tagName).toBe("SPAN");
  });

  it("renders without shortcut (content only)", () => {
    render(
      <Tooltip content="Just text">
        <button>btn</button>
      </Tooltip>,
    );
    const tooltip = screen.getByRole("tooltip");
    expect(tooltip.textContent).toBe("Just text");
    expect(tooltip.querySelectorAll("kbd")).toHaveLength(0);
  });
});

describe("Tooltip — Mac platform", () => {
  beforeEach(() => {
    mockIsMac.mockReturnValue(true);
  });

  it("renders ⌘. as single kbd for cmd modifier", () => {
    render(
      <Tooltip content="Both" shortcut={{ key: ".", modifier: "cmd" }}>
        <button>btn</button>
      </Tooltip>,
    );
    const kbds = screen.getByRole("tooltip").querySelectorAll("kbd");
    expect(kbds).toHaveLength(1);
    expect(kbds[0].textContent).toBe("\u2318.");
  });

  it("renders ⇧J for shift modifier", () => {
    render(
      <Tooltip content="Extend" shortcut={{ key: "j", modifier: "shift" }}>
        <button>btn</button>
      </Tooltip>,
    );
    const kbds = screen.getByRole("tooltip").querySelectorAll("kbd");
    expect(kbds).toHaveLength(1);
    expect(kbds[0].textContent).toBe("\u21E7J");
  });
});

describe("Tooltip — non-Mac platform", () => {
  beforeEach(() => {
    mockIsMac.mockReturnValue(false);
  });

  it("renders Ctrl + . with separate kbds for cmd modifier", () => {
    render(
      <Tooltip content="Both" shortcut={{ key: ".", modifier: "cmd" }}>
        <button>btn</button>
      </Tooltip>,
    );
    const tooltip = screen.getByRole("tooltip");
    const kbds = Array.from(tooltip.querySelectorAll("kbd")).map(
      (k) => k.textContent,
    );
    expect(kbds).toContain("Ctrl");
    expect(kbds).toContain(".");
    const seps = Array.from(tooltip.querySelectorAll(".help-key-sep")).map(
      (s) => s.textContent,
    );
    expect(seps).toContain("+");
  });

  it("renders Shift + J for shift modifier", () => {
    render(
      <Tooltip content="Extend" shortcut={{ key: "j", modifier: "shift" }}>
        <button>btn</button>
      </Tooltip>,
    );
    const tooltip = screen.getByRole("tooltip");
    const kbds = Array.from(tooltip.querySelectorAll("kbd")).map(
      (k) => k.textContent,
    );
    expect(kbds).toContain("Shift");
    expect(kbds).toContain("J");
  });
});
