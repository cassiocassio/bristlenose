import { act } from "@testing-library/react";
import { announce } from "./announce";
import { toast } from "./toast";

vi.mock("./announce", () => ({ announce: vi.fn() }));

const mockAnnounce = vi.mocked(announce);

describe("toast", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("speaks its message, since a toast is often the only sign an action happened", () => {
    act(() => toast("Copied"));
    expect(mockAnnounce).toHaveBeenCalledTimes(1);
    expect(mockAnnounce).toHaveBeenCalledWith("Copied");
  });

  it("speaks the bare message, never the kind's glyph", () => {
    act(() => toast("Couldn't save", 4000, "error"));
    expect(mockAnnounce).toHaveBeenCalledWith("Couldn't save");
  });
});
