import { fireEvent, render, screen } from "@testing-library/react";
import { Footer } from "./Footer";
import type { HealthResponse } from "../utils/health";

const HEALTH: HealthResponse = {
  status: "ok",
  version: "1.2.3",
  links: {
    github_issues_url: "https://example.com/issues/new",
  },
  feedback: {
    enabled: true,
    url: "https://example.com/feedback",
  },
  telemetry: {
    enabled: true,
    url: "https://example.com/telemetry",
  },
};

describe("Footer", () => {
  it("uses configured bug-report URL", () => {
    render(<Footer health={HEALTH} />);
    expect(screen.getByRole("link", { name: "Report a bug" })).toHaveAttribute(
      "href",
      "https://example.com/issues/new",
    );
  });

  it("opens feedback when clicking feedback link", () => {
    const onOpenFeedback = vi.fn();
    render(<Footer health={HEALTH} onOpenFeedback={onOpenFeedback} />);
    fireEvent.click(screen.getByText("Feedback"));
    expect(onOpenFeedback).toHaveBeenCalledOnce();
  });

  it("opens help when clicking keyboard hint", () => {
    const onToggleHelp = vi.fn();
    render(<Footer health={HEALTH} onToggleHelp={onToggleHelp} />);
    fireEvent.click(screen.getByRole("button", { name: /\? for Help/ }));
    expect(onToggleHelp).toHaveBeenCalledOnce();
  });

  it("hides feedback link when feedback is disabled", () => {
    render(
      <Footer
        health={{
          ...HEALTH,
          feedback: { ...HEALTH.feedback, enabled: false },
        }}
      />,
    );
    expect(screen.queryByText("Feedback")).toBeNull();
  });
});
