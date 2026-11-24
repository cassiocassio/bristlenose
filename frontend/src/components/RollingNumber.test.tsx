import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import { RollingNumber } from "./RollingNumber";

// The odometer count (owner, 24 Nov 2026): only the changed digits roll, up when the
// count grows and down when it shrinks, and the text is only ever the current value.

describe("RollingNumber", () => {
  it("draws a still number when it first appears", () => {
    const { container } = render(<RollingNumber value={8} />);
    expect(container.textContent).toBe("8");
    expect(container.querySelector(".bn-roll-col")).toBeNull();
  });

  it("rolls only the digits that changed, up when the count grows", () => {
    const { container, rerender } = render(<RollingNumber value={18} />);
    rerender(<RollingNumber value={19} />);
    expect(container.textContent).toBe("19");
    const cols = container.querySelectorAll(".bn-roll-digit");
    expect(cols).toHaveLength(1);
    expect(cols[0]).toHaveClass("bn-roll-digit--up");
    expect(cols[0]).toHaveAttribute("data-from", "8");
  });

  it("rolls down when the count shrinks, a digit that goes away included", () => {
    const { container, rerender } = render(<RollingNumber value={10} />);
    rerender(<RollingNumber value={9} />);
    expect(container.textContent).toBe("9");
    const cols = [...container.querySelectorAll(".bn-roll-digit")];
    expect(cols.map((c) => c.getAttribute("data-from"))).toEqual(["1", "0"]);
    cols.forEach((c) => expect(c).toHaveClass("bn-roll-digit--down"));
  });

  it("starts the roll again on each change", () => {
    const { container, rerender } = render(<RollingNumber value={3} />);
    rerender(<RollingNumber value={4} />);
    const first = container.querySelector(".bn-roll-col");
    rerender(<RollingNumber value={5} />);
    expect(container.querySelector(".bn-roll-col")).not.toBe(first);
    expect(container.querySelector(".bn-roll-digit")).toHaveAttribute("data-from", "4");
  });
});
