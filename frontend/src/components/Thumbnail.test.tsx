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

  it("contains a play icon when no thumbnailUrl", () => {
    render(<Thumbnail hasMedia={true} data-testid="thumb" />);
    const el = screen.getByTestId("thumb");
    const icon = el.querySelector(".bn-play-icon");
    expect(icon).not.toBeNull();
    expect(icon!.textContent).toBe("\u25B6");
    expect(el.querySelector("img")).toBeNull();
  });

  it("renders an img when thumbnailUrl is provided", () => {
    render(
      <Thumbnail
        hasMedia={true}
        thumbnailUrl="/report/assets/thumbnails/s1.jpg"
        data-testid="thumb"
      />,
    );
    const el = screen.getByTestId("thumb");
    const img = el.querySelector("img");
    expect(img).not.toBeNull();
    expect(img!.getAttribute("src")).toBe("/report/assets/thumbnails/s1.jpg");
    expect(img!.getAttribute("loading")).toBe("lazy");
    // Play icon should not be present when image is shown.
    expect(el.querySelector(".bn-play-icon")).toBeNull();
  });

  it("shows play icon when thumbnailUrl is undefined", () => {
    render(
      <Thumbnail hasMedia={true} thumbnailUrl={undefined} data-testid="thumb" />,
    );
    const el = screen.getByTestId("thumb");
    expect(el.querySelector(".bn-play-icon")).not.toBeNull();
    expect(el.querySelector("img")).toBeNull();
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
