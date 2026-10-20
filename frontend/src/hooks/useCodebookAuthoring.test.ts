/**
 * A codebook edit that does not save says so (R6).
 *
 * Renaming, creating, deleting, moving and merging tags and groups went to the
 * console only, so a refused rename (a name another tag holds is a 409) looked
 * like nothing happened. Each failure now says "Couldn't save" and re-reads the
 * codebook, so the screen shows what the server holds.
 */
import { act, renderHook } from "@testing-library/react";
import { useCodebookAuthoring } from "./useCodebookAuthoring";
import type { CodebookGroupResponse, CodebookTagResponse } from "../utils/types";

vi.mock("../utils/api", () => ({
  createCodebookGroup: vi.fn(() => Promise.resolve({ id: 9 })),
  createCodebookTag: vi.fn(() => Promise.resolve({})),
  deleteCodebookGroup: vi.fn(() => Promise.resolve()),
  deleteCodebookTag: vi.fn(() => Promise.resolve()),
  mergeCodebookTags: vi.fn(() => Promise.resolve({})),
  updateCodebookGroup: vi.fn(() => Promise.resolve()),
  updateCodebookTag: vi.fn(() => Promise.resolve()),
  toastSaveFailed: vi.fn(),
}));

import {
  createCodebookGroup,
  createCodebookTag,
  deleteCodebookGroup,
  deleteCodebookTag,
  mergeCodebookTags,
  toastSaveFailed,
  updateCodebookGroup,
  updateCodebookTag,
} from "../utils/api";

const refused = Object.assign(new Error("PATCH 409"), { status: 409 });
const tag = { id: 1, name: "Trust" } as CodebookTagResponse;
const other = { id: 2, name: "Ease" } as CodebookTagResponse;
const group = { id: 5, name: "G", colour_set: "ux" } as CodebookGroupResponse;
const settle = () => new Promise((r) => setTimeout(r, 0));

function setup() {
  const onChanged = vi.fn();
  const { result } = renderHook(() => useCodebookAuthoring({ groups: [group], onChanged }));
  return { result, onChanged };
}

beforeEach(() => vi.clearAllMocks());

const cases: Array<[string, unknown, (a: ReturnType<typeof setup>["result"]) => void]> = [
  ["rename a tag", updateCodebookTag, (r) => r.current.groupProps.onRenameTag(tag, "Ease")],
  ["create a tag", createCodebookTag, (r) => r.current.groupProps.onCreateTag("New", 5)],
  ["delete a tag", deleteCodebookTag, (r) => r.current.groupProps.onDeleteTag(tag)],
  ["rename a group", updateCodebookGroup, (r) => r.current.groupProps.onUpdateGroup(5, { subtitle: "s" })],
  ["delete a group", deleteCodebookGroup, (r) => r.current.groupProps.onDeleteGroup(group)],
  ["create a group", createCodebookGroup, (r) => r.current.onCreateGroup()],
  ["move a tag", updateCodebookTag, (r) => {
    r.current.groupProps.onDragStart(tag, 5);
    r.current.groupProps.onDropTag(6);
  }],
];

describe("a codebook edit that does not save says so", () => {
  it.each(cases)("%s", async (_name, fn, act_) => {
    vi.mocked(fn as () => Promise<unknown>).mockImplementationOnce(() => Promise.reject(refused));
    const { result, onChanged } = setup();
    act(() => act_(result));
    await settle();
    expect(toastSaveFailed).toHaveBeenCalledTimes(1);
    expect(toastSaveFailed).toHaveBeenCalledWith(refused);
    expect(onChanged).toHaveBeenCalledTimes(1); // re-read: the screen shows what saved
  });

  it("merge two tags", async () => {
    vi.mocked(mergeCodebookTags).mockImplementationOnce(() => Promise.reject(refused));
    const { result, onChanged } = setup();
    act(() => {
      result.current.groupProps.onDragStart(tag, 5);
    });
    act(() => result.current.groupProps.onMergeDrop(other));
    act(() => result.current.onConfirmMerge());
    await settle();
    expect(toastSaveFailed).toHaveBeenCalledTimes(1);
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("a group made by a drop whose move fails is still shown", async () => {
    vi.mocked(updateCodebookTag).mockImplementationOnce(() => Promise.reject(refused));
    const { result, onChanged } = setup();
    act(() => result.current.groupProps.onDragStart(tag, 5));
    act(() => result.current.onDropNewGroup({ preventDefault: () => {} } as React.DragEvent));
    await settle();
    expect(toastSaveFailed).toHaveBeenCalledTimes(1);
    expect(onChanged).toHaveBeenCalledTimes(1);
  });

  it("a write that saves says nothing", async () => {
    const { result, onChanged } = setup();
    act(() => result.current.groupProps.onRenameTag(tag, "Ease"));
    await settle();
    expect(toastSaveFailed).not.toHaveBeenCalled();
    expect(onChanged).toHaveBeenCalledTimes(1);
  });
});
