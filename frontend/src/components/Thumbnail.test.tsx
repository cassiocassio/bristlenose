import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Thumbnail } from "./Thumbnail";

describe("Thumbnail", () => {
  it("renders nothing when hasMedia is false", () => {
    const { container } = render(<Thumbnail hasMedia={false} />);
    expect(container.innerHTML).toBe("");
  });

  it("renders a video thumb container when hasMedia is true", () => {
    render(<Thumbnail hasMedia={true} data-testid="thumb" />);
    const el = screen.getByTestId("thumb");
    expect(el.className).toBe("bn-video-thumb");
  });

  it("contains a play icon", () => {
    render(<Thumbnail hasMedia={true} data-testid="thumb" />);
    const el = screen.getByTestId("thumb");
    const icon = el.querySelector(".bn-play-icon");
    expect(icon).not.toBeNull();
    expect(icon!.textContent).toBe("\u25B6");
  });

  it("appends custom className", () => {
    render(<Thumbnail hasMedia={true} className="extra" data-testid="thumb" />);
    expect(screen.getByTestId("thumb").className).toBe("bn-video-thumb extra");
  });

  it("supports data-testid", () => {
    render(<Thumbnail hasMedia={true} data-testid="my-thumb" />);
    expect(screen.getByTestId("my-thumb")).toBeDefined();
  });
});
