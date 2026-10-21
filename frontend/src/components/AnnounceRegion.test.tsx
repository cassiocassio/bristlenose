import { render } from "@testing-library/react";
import { AnnounceRegion } from "./AnnounceRegion";
import { announce } from "../utils/announce";

describe("AnnounceRegion", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("lives outside the app root, so a modal's inert root does not silence it", () => {
    const { unmount } = render(
      <div id="bn-app-root" inert>
        <AnnounceRegion />
      </div>,
    );
    const region = document.querySelector('[role="status"][aria-live="polite"]');
    expect(region).not.toBeNull();
    expect(region!.closest("[inert]")).toBeNull();
    unmount();
  });

  it("is the region announce() speaks into", () => {
    vi.useFakeTimers();
    const { unmount } = render(<AnnounceRegion />);
    announce("Copied");
    vi.advanceTimersByTime(16);
    const region = document.querySelector('[role="status"][aria-live="polite"]');
    expect(region).toHaveTextContent("Copied");
    unmount();
  });
});
