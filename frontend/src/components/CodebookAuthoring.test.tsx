import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MergeConfirm } from "./CodebookAuthoring";
import type { CodebookTagResponse } from "../utils/types";

const tag = (id: number, name: string): CodebookTagResponse => ({
  id,
  name,
  count: 1,
  colour_index: 0,
});

const noop = () => {};

describe("MergeConfirm", () => {
  it("renders a hostile tag name as text, never as markup", () => {
    const hostile = "<img src=x onerror=alert(1)>";
    render(
      <MergeConfirm
        pending={{ source: tag(1, hostile), target: tag(2, "Navigation") }}
        onConfirm={noop}
        onCancel={noop}
      />,
    );
    const dialog = screen.getByTestId("bn-merge-confirm");
    expect(document.querySelector("img")).toBeNull();
    // The name still reads, inside the copy's own <strong>.
    const strongs = dialog.querySelectorAll("strong");
    expect(Array.from(strongs, (s) => s.textContent)).toContain(hostile);
  });
});
