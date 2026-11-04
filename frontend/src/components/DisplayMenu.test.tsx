import { render, screen, fireEvent, act } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { DisplayMenu } from "./DisplayMenu";
import {
  _resetDisplayPrefs,
  getDisplayPrefs,
  setDisplayPref,
} from "../contexts/DisplayPrefsStore";
import { _resetFocusMode, isFocusMode, setFocusMode } from "../contexts/FocusModeStore";

beforeEach(() => {
  localStorage.clear();
  _resetDisplayPrefs();
  _resetFocusMode();
});

afterEach(() => {
  _resetDisplayPrefs();
  _resetFocusMode();
});

function openMenu() {
  render(<DisplayMenu />);
  fireEvent.click(screen.getByTestId("bn-toolbar-display"));
  return screen.getByTestId("bn-display-menu");
}

describe("DisplayMenu", () => {
  it("opens a menu with the current choices ticked", () => {
    const menu = openMenu();
    expect(menu).toHaveAttribute("role", "menu");
    expect(screen.getByTestId("bn-display-layout-columns")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("bn-display-layout-single")).toHaveAttribute("aria-checked", "false");
    expect(screen.getByTestId("bn-display-density-normal")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("bn-display-breaks")).toHaveAttribute("aria-checked", "false");
  });

  it("uses radio rows for Layout and Density and checkbox rows for the two switches", () => {
    openMenu();
    expect(screen.getAllByRole("menuitemradio")).toHaveLength(5);
    expect(screen.getAllByRole("menuitemcheckbox")).toHaveLength(2);
  });

  it("stays open when a choice is made, and the choice sticks", () => {
    openMenu();
    fireEvent.click(screen.getByTestId("bn-display-layout-single"));
    expect(screen.getByTestId("bn-display-menu")).toBeInTheDocument();
    expect(getDisplayPrefs().layout).toBe("single");
    expect(screen.getByTestId("bn-display-layout-single")).toHaveAttribute("aria-checked", "true");
    expect(screen.getByTestId("bn-display-layout-columns")).toHaveAttribute("aria-checked", "false");
  });

  it("stays open through a density choice, the breaks switch and the Focus Mode switch", () => {
    openMenu();
    fireEvent.click(screen.getByTestId("bn-display-density-spacious"));
    fireEvent.click(screen.getByTestId("bn-display-breaks"));
    fireEvent.click(screen.getByTestId("bn-display-focus-mode"));
    expect(screen.getByTestId("bn-display-menu")).toBeInTheDocument();
    expect(getDisplayPrefs()).toMatchObject({ density: 1, breaks: "on" });
    expect(isFocusMode()).toBe(true);
    expect(screen.getByTestId("bn-display-focus-mode")).toHaveAttribute("aria-checked", "true");
  });

  it("toggles the breaks switch off again", () => {
    openMenu();
    fireEvent.click(screen.getByTestId("bn-display-breaks"));
    fireEvent.click(screen.getByTestId("bn-display-breaks"));
    expect(getDisplayPrefs().breaks).toBe("off");
  });

  it("closes on Escape and on a click outside", () => {
    openMenu();
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByTestId("bn-display-menu")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("bn-toolbar-display"));
    expect(screen.getByTestId("bn-display-menu")).toBeInTheDocument();
    fireEvent.mouseDown(document.body);
    expect(screen.queryByTestId("bn-display-menu")).not.toBeInTheDocument();
  });

  it("reads the saved value again each time it opens", () => {
    render(<DisplayMenu />);
    fireEvent.click(screen.getByTestId("bn-toolbar-display"));
    fireEvent.keyDown(document, { key: "Escape" });
    act(() => setDisplayPref("density", 0));
    fireEvent.click(screen.getByTestId("bn-toolbar-display"));
    expect(screen.getByTestId("bn-display-density-compact")).toHaveAttribute("aria-checked", "true");
  });

  it("keeps in step with Focus Mode switched elsewhere (the toolbar button, the z key)", () => {
    openMenu();
    expect(screen.getByTestId("bn-display-focus-mode")).toHaveAttribute("aria-checked", "false");
    act(() => setFocusMode(true));
    expect(screen.getByTestId("bn-display-focus-mode")).toHaveAttribute("aria-checked", "true");
  });

  it("gives focus back to the button on Escape, but leaves it where the reader clicked on an outside click", () => {
    render(
      <>
        <input data-testid="elsewhere" />
        <DisplayMenu />
      </>,
    );
    const trigger = screen.getByTestId("bn-toolbar-display");
    fireEvent.click(trigger);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(trigger).toHaveFocus();

    fireEvent.click(trigger);
    const elsewhere = screen.getByTestId("elsewhere");
    elsewhere.focus();
    fireEvent.mouseDown(elsewhere);
    expect(screen.queryByTestId("bn-display-menu")).not.toBeInTheDocument();
    expect(elsewhere).toHaveFocus();
  });

  it("ticks no density row when the value sits between the stops (set on the Mac slider)", () => {
    act(() => setDisplayPref("density", 0.3));
    openMenu();
    for (const stop of ["compact", "normal", "spacious"]) {
      expect(screen.getByTestId(`bn-display-density-${stop}`)).toHaveAttribute("aria-checked", "false");
    }
  });

  it("gives every Layout and Density row an icon, and the two switches none", () => {
    openMenu();
    for (const id of ["bn-display-layout-columns", "bn-display-density-compact", "bn-display-density-spacious"]) {
      // Two svgs: the tick (only when chosen) and the row's own icon, which is always there.
      expect(screen.getByTestId(id).querySelector("svg[aria-hidden='true']")).not.toBeNull();
    }
    expect(screen.getByTestId("bn-display-breaks").querySelectorAll("svg").length).toBe(0);
    expect(screen.getByTestId("bn-display-focus-mode").querySelectorAll("svg").length).toBe(0);
  });

  it("does not take focus back after an outside click that follows a choice made in the menu", () => {
    render(
      <>
        <input data-testid="elsewhere" />
        <DisplayMenu />
      </>,
    );
    fireEvent.click(screen.getByTestId("bn-toolbar-display"));
    // The menu stays open through a choice made with the mouse...
    const row = screen.getByTestId("bn-display-layout-single");
    fireEvent.mouseDown(row);
    fireEvent.click(row);
    expect(screen.getByTestId("bn-display-menu")).toBeInTheDocument();
    // ...and a later click elsewhere must still leave focus where the reader put it.
    const elsewhere = screen.getByTestId("elsewhere");
    elsewhere.focus();
    fireEvent.mouseDown(elsewhere);
    expect(screen.queryByTestId("bn-display-menu")).not.toBeInTheDocument();
    expect(elsewhere).toHaveFocus();
  });

  it("names the Layout and Density radio sets for assistive technology", () => {
    openMenu();
    expect(screen.getByRole("group", { name: "Layout" })).toBeInTheDocument();
    expect(screen.getByRole("group", { name: "Density" })).toBeInTheDocument();
  });

  it("moves between rows with the arrow keys", () => {
    openMenu();
    const first = screen.getByTestId("bn-display-layout-columns");
    first.focus();
    fireEvent.keyDown(first, { key: "ArrowDown" });
    expect(screen.getByTestId("bn-display-layout-single")).toHaveFocus();
  });
});
