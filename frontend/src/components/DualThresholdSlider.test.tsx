import { render, screen, fireEvent } from "@testing-library/react";
import { DualThresholdSlider } from "./DualThresholdSlider";
import { ConfidenceHistogram } from "./ConfidenceHistogram";
import type { ProposedTagResponse } from "../utils/types";

// N185: the slider's 0.05 steps must be the numbers they are labelled as.
// `Math.round(v / 0.05) * 0.05` leaves 0.30000000000000004 and the like at 7
// of the 21 stops, and the server compares what is sent with >= and <, so a
// proposal at exactly 0.30 went to Exclude and one at 0.85 stayed Tentative.
const STOPS = Array.from({ length: 21 }, (_, n) => n / 20);

describe("DualThresholdSlider steps", () => {
  it("every keyboard step up lands exactly on a 0.05 stop", () => {
    for (let n = 1; n < 20; n++) {
      const onUpper = vi.fn();
      const { unmount } = render(
        <DualThresholdSlider lower={0} upper={STOPS[n]} onLowerChange={vi.fn()} onUpperChange={onUpper} />,
      );
      fireEvent.keyDown(screen.getByTestId("bn-threshold-upper"), { key: "ArrowRight" });
      expect(onUpper).toHaveBeenCalledWith(STOPS[n + 1]);
      unmount();
    }
  });

  it("every keyboard step down lands exactly on a 0.05 stop", () => {
    for (let n = 1; n < 20; n++) {
      const onLower = vi.fn();
      const { unmount } = render(
        <DualThresholdSlider lower={STOPS[n]} upper={1} onLowerChange={onLower} onUpperChange={vi.fn()} />,
      );
      fireEvent.keyDown(screen.getByTestId("bn-threshold-lower"), { key: "ArrowLeft" });
      expect(onLower).toHaveBeenCalledWith(STOPS[n - 1]);
      unmount();
    }
  });

  it("the thumbs stopped one step apart sit on exact stops, whichever way they are pushed", () => {
    // clamp(…, upper - 0.05) and clamp(…, lower + 0.05) carry the same drift
    for (let n = 1; n < 19; n++) {
      const onLower = vi.fn();
      const onUpper = vi.fn();
      const { unmount } = render(
        <DualThresholdSlider
          lower={STOPS[n]}
          upper={STOPS[n + 1]}
          onLowerChange={onLower}
          onUpperChange={onUpper}
        />,
      );
      fireEvent.keyDown(screen.getByTestId("bn-threshold-lower"), { key: "ArrowRight" });
      fireEvent.keyDown(screen.getByTestId("bn-threshold-upper"), { key: "ArrowLeft" });
      expect(onLower).toHaveBeenCalledWith(STOPS[n]);
      expect(onUpper).toHaveBeenCalledWith(STOPS[n + 1]);
      unmount();
    }
  });

  it("a step from the default upper 0.70 reaches 0.85 exactly in three presses", () => {
    let upper = 0.7;
    const onUpper = vi.fn((v: number) => {
      upper = v;
    });
    const { rerender } = render(
      <DualThresholdSlider lower={0.3} upper={upper} onLowerChange={vi.fn()} onUpperChange={onUpper} />,
    );
    for (let i = 0; i < 3; i++) {
      fireEvent.keyDown(screen.getByTestId("bn-threshold-upper"), { key: "ArrowRight" });
      rerender(
        <DualThresholdSlider lower={0.3} upper={upper} onLowerChange={vi.fn()} onUpperChange={onUpper} />,
      );
    }
    expect(upper).toBe(0.85);
  });
});

describe("DualThresholdSlider drag", () => {
  it("a thumb dragged against the other lands on an exact stop", () => {
    const onLower = vi.fn();
    const { container } = render(
      <DualThresholdSlider lower={0.3} upper={0.7} onLowerChange={onLower} onUpperChange={vi.fn()} />,
    );
    const track = container.querySelector(".threshold-slider-track") as HTMLElement;
    track.getBoundingClientRect = () =>
      ({ left: 0, width: 1000, top: 0, height: 10, right: 1000, bottom: 10, x: 0, y: 0 }) as DOMRect;
    const thumb = screen.getByTestId("bn-threshold-lower");
    thumb.setPointerCapture = vi.fn();
    fireEvent.pointerDown(thumb, { pointerId: 1 });
    // far right: pushed against upper - 0.05, which is 0.6499999999999999
    fireEvent(thumb, new MouseEvent("pointermove", { clientX: 900 }));
    expect(onLower).toHaveBeenCalledWith(0.65);
  });

  it("aria bounds are exact too", () => {
    render(
      <DualThresholdSlider lower={0.3} upper={0.7} onLowerChange={vi.fn()} onUpperChange={vi.fn()} />,
    );
    expect(screen.getByTestId("bn-threshold-lower")).toHaveAttribute("aria-valuemax", "0.65");
  });
});

function proposal(id: number, confidence: number): ProposedTagResponse {
  return {
    id,
    quote_id: id,
    dom_id: `q-${id}`,
    session_id: "s1",
    speaker_code: "P1",
    start_timecode: 0,
    quote_text: "q",
    tag_definition_id: 1,
    tag_name: "T",
    group_name: "G",
    colour_set: "emo",
    colour_index: 0,
    confidence,
    rationale: "",
    status: "pending",
  };
}

describe("ConfidenceHistogram bins at the 0.05 grid", () => {
  it("puts a proposal at exactly a bin's lower edge in that bin, not the one below", () => {
    // 0.15, 0.3, 0.35, 0.6, 0.7, 0.95: Math.floor(c / 0.05) put each one bin low.
    const edges = [0.15, 0.3, 0.35, 0.6, 0.7, 0.95];
    edges.forEach((c, i) => {
      const { container, unmount } = render(
        <ConfidenceHistogram proposals={[proposal(i + 1, c)]} lower={0.3} upper={0.7} />,
      );
      const bins = container.querySelectorAll(".threshold-histogram-bin");
      const filled = Array.from(bins).findIndex((b) => b.children.length > 0);
      expect(filled).toBe(Math.round(c * 20));
      unmount();
    });
  });

  it("a confidence below zero does not throw", () => {
    expect(() =>
      render(<ConfidenceHistogram proposals={[proposal(1, -0.1)]} lower={0.3} upper={0.7} />),
    ).not.toThrow();
  });

  it("draws a bar at exactly the upper threshold green, as Apply accepts it", () => {
    // five in one bin forces bar mode, where the zone colour is shown
    const five = [1, 2, 3, 4, 5].map((id) => proposal(id, 0.7));
    const { container } = render(<ConfidenceHistogram proposals={five} lower={0.3} upper={0.7} />);
    expect(container.querySelectorAll(".threshold-histogram-bar--green")).toHaveLength(1);
    expect(container.querySelectorAll(".threshold-histogram-bar--amber")).toHaveLength(0);
  });
});
