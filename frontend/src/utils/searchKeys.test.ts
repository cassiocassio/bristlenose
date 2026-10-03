import { describe, expect, it } from "vitest";
import { backspaceAction, highlightedRow, moveHighlight, tokenKey } from "./searchKeys";
import { personToken, tagToken } from "./searchTokens";

describe("searchKeys — the same decisions as the Mac field's SearchFieldKeys", () => {
  const ids = ["text", "person:p3", "tag:zoning"];

  it("↓ / ↑ move by row id and wrap; no highlight means the first row", () => {
    expect(moveHighlight(null, 1, ids)).toBe("person:p3");
    expect(moveHighlight(null, -1, ids)).toBe("tag:zoning");
    expect(moveHighlight("tag:zoning", 1, ids)).toBe("text");
    expect(moveHighlight("text", -1, ids)).toBe("tag:zoning");
    expect(moveHighlight("text", 1, [])).toBeNull();
  });

  it("the highlight follows its row, not its position; a row that went hands it back to the first", () => {
    expect(highlightedRow("person:p3", ["text", "tag:zoning", "person:p3"])).toBe("person:p3");
    expect(highlightedRow("person:p3", ["text", "tag:zoning"])).toBe("text");
    expect(highlightedRow(null, [])).toBeNull();
  });

  it("⌫ in an empty field selects the last token, then removes it", () => {
    const tokens = [personToken("p3", undefined, "Priya"), tagToken({ name: "Zoning" })];
    const last = tokenKey(tokens[1]);
    expect(backspaceAction("", tokens, null)).toEqual({ kind: "select", key: last });
    expect(backspaceAction("", tokens, last)).toEqual({ kind: "remove", token: tokens[1] });
    expect(backspaceAction("ab", tokens, last)).toEqual({ kind: "passThrough" });
    expect(backspaceAction("", [], null)).toEqual({ kind: "passThrough" });
  });

  it("a tag token's key is its folded name, as the store compares tags", () => {
    expect(tokenKey(tagToken({ name: "Zoë " }))).toBe(tokenKey(tagToken({ name: "zoe" })));
  });
});
