import { render, screen, fireEvent } from "@testing-library/react";
import { NewBadge } from "./NewBadge";

const KEY = "section-cluster-5";
const STORAGE = "bn-new-dismissed:" + KEY;

beforeEach(() => {
  localStorage.clear();
});

describe("NewBadge", () => {
  it("renders the marker when isNew and not dismissed", () => {
    render(<NewBadge isNew dismissKey={KEY} newSince="t1" />);
    expect(screen.getByText("New")).toBeInTheDocument();
  });

  it("renders nothing when not isNew", () => {
    render(<NewBadge isNew={false} dismissKey={KEY} newSince="t1" />);
    expect(screen.queryByText("New")).not.toBeInTheDocument();
  });

  it("renders nothing when newSince is null (no new material generation)", () => {
    render(<NewBadge isNew dismissKey={KEY} newSince={null} />);
    expect(screen.queryByText("New")).not.toBeInTheDocument();
  });

  it("evaporates on click and persists the dismissal for this token", () => {
    render(<NewBadge isNew dismissKey={KEY} newSince="t1" />);
    fireEvent.click(screen.getByText("New"));
    expect(screen.queryByText("New")).not.toBeInTheDocument();
    expect(localStorage.getItem(STORAGE)).toBe("t1");
  });

  it("stays dismissed on remount for the same token", () => {
    localStorage.setItem(STORAGE, "t1");
    render(<NewBadge isNew dismissKey={KEY} newSince="t1" />);
    expect(screen.queryByText("New")).not.toBeInTheDocument();
  });

  it("re-shows when a genuinely-fresh import brings a new token", () => {
    localStorage.setItem(STORAGE, "t1"); // dismissed the previous generation
    render(<NewBadge isNew dismissKey={KEY} newSince="t2" />);
    expect(screen.getByText("New")).toBeInTheDocument();
  });
});
