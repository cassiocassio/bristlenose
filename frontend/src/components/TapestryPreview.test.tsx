import { describe, expect, it, vi } from "vitest";
import { fireEvent, render } from "@testing-library/react";
import { TapestryPreview } from "./TapestryPreview";
import type { TapestrySession } from "../utils/types";

const session: TapestrySession = {
  session_id: "s1",
  duration_seconds: 600,
  turns: [
    { t0: 0, t1: 60, speaker: "m1", colour: "#334455" },
    { t0: 60, t1: 300, speaker: "p1", colour: "#9fceef" },
    { t0: 300, t1: 360, speaker: "m1", colour: null },
    { t0: 360, t1: 600, speaker: "p2", colour: null },
  ],
  sections: [],
  quotes: [],
};
const isTeam = (tn: TapestrySession["turns"][number]) => tn.speaker.startsWith("m");

describe("TapestryPreview", () => {
  it("draws every participant's turns in one lane, in scene colour, and no team turn", () => {
    render(<TapestryPreview session={session} width={700} isTeam={isTeam} onOpen={() => {}} />);
    const clips = [...document.querySelectorAll<SVGRectElement>(".bn-tp-pv-clip")];
    expect(clips).toHaveLength(2);
    expect(clips[0].style.fill).toMatch(/#9fceef|rgb\(159, 206, 239\)/);
    expect(clips[1].style.fill).toBe(""); // no scene colour: the stylesheet's neutral
    expect(document.querySelectorAll(".bn-tp-pv-edge")).toHaveLength(2);
  });

  it("spans the row, its track starting where the open timeline's tracks start", () => {
    render(<TapestryPreview session={session} width={700} isTeam={isTeam} onOpen={() => {}} />);
    const track = document.querySelector(".bn-tp-pv-track")!;
    expect(track.getAttribute("x")).toBe("82");
    expect(Number(track.getAttribute("width"))).toBeCloseTo(700 - 82 - 14);
  });

  it("has no text and stays out of assistive technology: the disclosure is the accessible route", () => {
    const { container } = render(<TapestryPreview session={session} width={700} isTeam={isTeam} onOpen={() => {}} />);
    expect(container.textContent).toBe("");
    expect(container.firstElementChild).toHaveAttribute("aria-hidden", "true");
  });

  it("opens on click, every row on Option-click, and keeps the click from the row", () => {
    const onOpen = vi.fn();
    const onRow = vi.fn();
    render(
      // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions
      <div onClick={onRow}>
        <TapestryPreview session={session} width={700} isTeam={isTeam} onOpen={onOpen} />
      </div>,
    );
    const strip = document.querySelector(".bn-tapestry-preview")!;
    fireEvent.click(strip);
    fireEvent.click(strip, { altKey: true });
    expect(onOpen.mock.calls).toEqual([[false], [true]]);
    expect(onRow).not.toHaveBeenCalled();
  });

  it("draws nothing without a width or a duration", () => {
    const { container, rerender } = render(<TapestryPreview session={session} width={50} isTeam={isTeam} onOpen={() => {}} />);
    expect(container.firstChild).toBeNull();
    rerender(<TapestryPreview session={{ ...session, duration_seconds: 0 }} width={700} isTeam={isTeam} onOpen={() => {}} />);
    expect(container.firstChild).toBeNull();
  });
});
