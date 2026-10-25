/**
 * N183: the video map was read once, at mount, so a quote from a session that
 * arrived after the report opened (a run in progress; in the browser, any run) had a
 * timecode that played nothing. It is read again whenever a run lands, on the same
 * signal the lenses re-read on (`refreshKey`).
 */
import { useEffect } from "react";
import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, act, waitFor } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { PlayerProvider, usePlayer, hasRecording } from "./PlayerContext";
import { bumpRefreshKey, resetLastRunStore } from "./LastRunStore";

vi.mock("../utils/announce", () => ({ announce: vi.fn() }));
vi.mock("../shims/bridge", () => ({ postPlayerState: vi.fn() }));
vi.mock("../utils/api", () => ({
  apiGet: vi.fn(),
  apiGetText: vi.fn().mockRejectedValue(new Error("404")),
}));

import { apiGet } from "../utils/api";

const player: { seek: (pid: string, seconds: number) => void } = { seek: () => {} };
function Consumer() {
  const { seekTo } = usePlayer();
  useEffect(() => {
    player.seek = seekTo;
  }, [seekTo]);
  return null;
}

function mount() {
  const router = createMemoryRouter(
    [{ path: "/", element: <PlayerProvider><Consumer /></PlayerProvider> }],
    { initialEntries: ["/"] },
  );
  return render(<RouterProvider router={router} />);
}

describe("video map follows the run", () => {
  let openSpy: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    resetLastRunStore();
    vi.mocked(apiGet).mockReset();
    openSpy = vi.spyOn(window, "open").mockReturnValue({
      closed: false,
      postMessage: vi.fn(),
      focus: vi.fn(),
    } as unknown as Window);
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("a session added after the report opened plays once a run lands", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce({ video_map: { p1: "/media/one.mp4" } });
    mount();
    await waitFor(() => expect(hasRecording("p1")).toBe(true));

    // p2 does not exist yet
    act(() => player.seek("p2", 5));
    expect(openSpy).not.toHaveBeenCalled();

    vi.mocked(apiGet).mockResolvedValueOnce({
      video_map: { p1: "/media/one.mp4", p2: "/media/two.mp4" },
    });
    act(() => bumpRefreshKey());
    await waitFor(() => expect(hasRecording("p2")).toBe(true));

    act(() => player.seek("p2", 5));
    expect(openSpy).toHaveBeenCalledOnce();
    expect(openSpy.mock.calls[0][0]).toContain("pid=p2");
  });

  it("a failed re-read keeps the map it has", async () => {
    vi.mocked(apiGet).mockResolvedValueOnce({ video_map: { p1: "/media/one.mp4" } });
    vi.spyOn(console, "warn").mockImplementation(() => {});
    mount();
    await waitFor(() => expect(hasRecording("p1")).toBe(true));

    vi.mocked(apiGet).mockRejectedValueOnce(new Error("offline"));
    act(() => bumpRefreshKey());
    await waitFor(() => expect(apiGet).toHaveBeenCalledTimes(2));
    await act(async () => {});

    expect(hasRecording("p1")).toBe(true);
  });
});
