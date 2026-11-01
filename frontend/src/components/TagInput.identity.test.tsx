/**
 * A tag picked from the list is committed as the row it is, never as a name two tags can share
 * (N146): a typed whole name means the researcher's own tag when they have one, the machine's
 * sentiment tags are never the answer to a typed name, and a name two tags share lists both.
 */
import { render, screen, fireEvent } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { TagInput } from "./TagInput";
import type { TagVocabularyGroup } from "./TagInput";

// The researcher's own group leads, as buildTagVocabulary orders it.
const GROUPS: TagVocabularyGroup[] = [
  {
    groupName: "Uncategorised",
    colourSet: "",
    frameworkId: null,
    tags: [{ name: "trust", colourIndex: 0, id: 7 }],
  },
  {
    groupName: "Trust & Safety",
    colourSet: "trust",
    frameworkId: "uxr",
    tags: [
      { name: "trust", colourIndex: 2, id: 9 },
      { name: "trustworthiness", colourIndex: 3, id: 10 },
    ],
  },
  {
    groupName: "Sentiment",
    colourSet: "emo",
    frameworkId: "sentiment",
    tags: [{ name: "frustration", colourIndex: 0, id: 20 }],
  },
];

function setup(onCommit = vi.fn()) {
  const utils = render(
    <TagInput
      vocabulary={["trust", "trustworthiness", "frustration"]}
      groupedVocabulary={GROUPS}
      onCommit={onCommit}
      onCancel={vi.fn()}
    />,
  );
  return { onCommit, ...utils };
}

describe("TagInput tag identity", () => {
  it("Return on a typed whole name commits the researcher's own tag", async () => {
    const { onCommit } = setup();
    await userEvent.type(screen.getByPlaceholderText("tag"), "trust{Enter}");
    expect(onCommit).toHaveBeenCalledWith("trust", {
      id: 7,
      groupName: "Uncategorised",
      colourSet: "",
      colourIndex: 0,
    });
  });

  it("a name two tags share lists both, the researcher's own first", async () => {
    const { container } = setup();
    await userEvent.type(screen.getByPlaceholderText("tag"), "trust");
    const items = [...container.querySelectorAll(".tag-suggest-item")];
    expect(items.map((i) => `${i.getAttribute("data-group")}:${i.textContent}`)).toEqual([
      "Uncategorised:trust",
      "Trust & Safety:trust",
      "Trust & Safety:trustworthiness",
    ]);
  });

  it("a name only one tag has is not listed back to the person who typed it", async () => {
    const { container } = setup();
    await userEvent.type(screen.getByPlaceholderText("tag"), "trustworthiness");
    expect(container.querySelectorAll(".tag-suggest-item")).toHaveLength(0);
  });

  it("choosing the other same-named row commits that row", async () => {
    const { onCommit, container } = setup();
    await userEvent.type(screen.getByPlaceholderText("tag"), "trust");
    fireEvent.mouseDown(container.querySelectorAll(".tag-suggest-item")[1]);
    expect(onCommit).toHaveBeenCalledWith("trust", {
      id: 9,
      groupName: "Trust & Safety",
      colourSet: "trust",
      colourIndex: 2,
    });
  });

  it("arrowing to a row and pressing Return commits that row", async () => {
    const { onCommit } = setup();
    await userEvent.type(screen.getByPlaceholderText("tag"), "trust{ArrowDown}{ArrowDown}{Enter}");
    expect(onCommit).toHaveBeenCalledWith(
      "trust",
      expect.objectContaining({ id: 9 }),
    );
  });

  it("a typed sentiment name is not the machine's sentiment tag", async () => {
    const { onCommit } = setup();
    await userEvent.type(screen.getByPlaceholderText("tag"), "frustration{Enter}");
    expect(onCommit).toHaveBeenCalledWith("frustration");
  });

  it("a typed name nobody has commits as a name alone", async () => {
    const { onCommit } = setup();
    await userEvent.type(screen.getByPlaceholderText("tag"), "wayfinding{Enter}");
    expect(onCommit).toHaveBeenCalledWith("wayfinding");
  });
});
