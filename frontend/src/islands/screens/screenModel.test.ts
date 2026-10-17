import { describe, expect, it } from "vitest";
import {
  screenRef, screensArrival, screensPath, screenStarts, screenTitle, stillUrl,
  type ScreenLike, type ScreenTabLike,
} from "./screenModel";

const tab = (session_id: string, visits: [number, number][], heading = ""): ScreenTabLike => ({
  session_id, t: visits[0]?.[0] ?? 0, crop: [0, 0, 1, 1], heading, visits,
});
const screen = (key: string, name: string, tabs: ScreenTabLike[]): ScreenLike => ({ key, name, tabs });

describe("screenTitle", () => {
  it("is the name, capitalised, unless the name is a path", () => {
    expect(screenTitle(screen("k", "shopping bag", []))).toBe("Shopping bag");
  });
  it("is a path's version heading, or every version's headings", () => {
    const s = screen("k", "/checkout/delivery", [tab("s1", [[0, 1]], "Delivery or collect"), tab("s2", [[0, 1]], "Lieferung")]);
    expect(screenTitle(s, s.tabs[1])).toBe("Lieferung");
    expect(screenTitle(s)).toBe("Delivery or collect · Lieferung");
  });
});

describe("screenRef", () => {
  it("is stable, and carries nothing of the key it stands for", () => {
    const key = "/account/orders/123-secret";
    expect(screenRef(key)).toBe(screenRef(key));
    expect(screenRef(key)).not.toBe(screenRef("/account/orders/124-secret"));
    expect(screensPath(key, "s1")).not.toContain("account");
    expect(screensPath(key, "s1")).toBe(`/report/screens/?screen=${screenRef(key)}&session=s1`);
  });
  it("is read back from the address", () => {
    expect(screensArrival(`?screen=${screenRef("x")}&session=s2`)).toEqual({ ref: screenRef("x"), session: "s2" });
    expect(screensArrival("?screen=abc")).toBeNull();
    expect(screensArrival("")).toBeNull();
  });
});

describe("screenStarts", () => {
  // Paragraphs every 10 s: 0–10, 10–20, 20–30, …
  const at = (sec: number) => (sec >= 0 && sec < 100 ? Math.floor(sec / 10) : null);

  it("puts each visit's start in the paragraph it began in, for this session only", () => {
    const starts = screenStarts(
      [screen("bag", "Bag", [tab("s1", [[12, 18]]), tab("s2", [[5, 9]])]), screen("home", "Home", [tab("s1", [[3, 11]])])],
      "s1", at,
    );
    expect([...starts.keys()]).toEqual([0, 1]);
    expect(starts.get(0)!.map((v) => v.screen.key)).toEqual(["home"]);
    expect(starts.get(1)!.map((v) => v.screen.key)).toEqual(["bag"]);
  });

  it("treats a return with nothing between as the same stay", () => {
    const starts = screenStarts([screen("bag", "Bag", [tab("s1", [[12, 15], [16, 30]])])], "s1", at);
    expect([...starts.keys()]).toEqual([1]);
  });

  it("marks a return after another screen as a new visit", () => {
    const starts = screenStarts(
      [screen("bag", "Bag", [tab("s1", [[12, 15], [40, 45]])]), screen("pay", "Pay", [tab("s1", [[22, 30]])])],
      "s1", at,
    );
    expect([...starts.keys()]).toEqual([1, 2, 4]);
  });

  it("lists two screens beginning in one paragraph in the order they began", () => {
    const starts = screenStarts(
      [screen("a", "A", [tab("s1", [[17, 18]])]), screen("b", "B", [tab("s1", [[11, 16]])])],
      "s1", at,
    );
    expect(starts.get(1)!.map((v) => v.screen.key)).toEqual(["b", "a"]);
  });

  it("treats two screens with one title as one place", () => {
    // Different addresses, one heading: a stay across them is one stay, and a paragraph names it once.
    const starts = screenStarts(
      [screen("a", "/list?page=1", [tab("s1", [[11, 13]], "Storage furniture")]),
       screen("b", "/list?page=2", [tab("s1", [[13, 15], [33, 35]], "Storage furniture")]),
       screen("c", "Kitchenware", [tab("s1", [[16, 18], [31, 32]])])],
      "s1", at,
    );
    expect(starts.get(1)!.map((v) => screenTitle(v.screen, v.tab))).toEqual(["Storage furniture", "Kitchenware"]);
    // Kitchenware at 31 s follows its own visit at 16 s with nothing between: the same stay.
    expect(starts.get(3)!.map((v) => screenTitle(v.screen, v.tab))).toEqual(["Storage furniture"]);
  });

  it("skips a visit no paragraph holds", () => {
    expect(screenStarts([screen("x", "X", [tab("s1", [[500, 510]])])], "s1", at).size).toBe(0);
  });
});

describe("stillUrl", () => {
  it("asks for a version's still at a width, with its crop", () => {
    expect(stillUrl({ ...tab("s 1", [[3, 4]]), crop: [0, 0.1, 1, 0.9] }, 280))
      .toBe("/screens/still?session_id=s%201&t=3&w=280&crop=0.0000,0.1000,1.0000,0.9000");
  });
});
