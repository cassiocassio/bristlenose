import { describe, expect, it } from "vitest";

import { countColumnStyle, countDigits } from "./countColumn";

describe("countDigits", () => {
  it("is the digit count of the widest number", () => {
    expect(countDigits([3, 12, 8])).toBe(2);
    expect(countDigits([128, 45, 7])).toBe(3);
    expect(countDigits([9])).toBe(1);
  });

  it("is one digit for an empty list or all zeros, so the column never collapses", () => {
    expect(countDigits([])).toBe(1);
    expect(countDigits([0, 0])).toBe(1);
  });

  it("steps up exactly at a digit boundary", () => {
    expect(countDigits([99])).toBe(2);
    expect(countDigits([100])).toBe(3);
  });
});

describe("countColumnStyle", () => {
  it("sets the width as --bn-count-digits for the CSS to read", () => {
    expect(countColumnStyle([32, 12])).toEqual({ "--bn-count-digits": 2 });
  });
});
