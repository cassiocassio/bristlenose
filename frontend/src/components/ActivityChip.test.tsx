import { render, screen, fireEvent } from "@testing-library/react";
import { ActivityChip } from "./ActivityChip";
import type { ActivityChipJob } from "./ActivityChip";

function makeJob(overrides: Partial<ActivityChipJob> = {}): ActivityChipJob {
  return {
    id: "autocode:garrett",
    label: "\u2726 AutoCoded 10 transcripts",
    status: "running",
    progressLabel: "3/10 transcripts",
    durationLabel: null,
    errorMessage: null,
    ...overrides,
  };
}

describe("ActivityChip", () => {
  it("renders spinner and progress while running", () => {
    render(<ActivityChip job={makeJob()} />);

    const chip = screen.getByTestId("bn-activity-chip");
    expect(chip).toBeInTheDocument();
    expect(chip).toHaveAttribute("data-status", "running");
    expect(chip.querySelector(".chip-spinner")).toBeInTheDocument();
    expect(screen.getByText(/3\/10 transcripts/)).toBeInTheDocument();
  });

  it("does not render close button while running", () => {
    render(<ActivityChip job={makeJob()} onDismiss={vi.fn()} />);

    expect(screen.queryByTestId("bn-activity-chip-close")).not.toBeInTheDocument();
  });

  it("renders checkmark and duration when completed", () => {
    render(
      <ActivityChip
        job={makeJob({ status: "completed", durationLabel: "1:23", progressLabel: null })}
      />,
    );

    const chip = screen.getByTestId("bn-activity-chip");
    expect(chip).toHaveAttribute("data-status", "completed");
    expect(chip.querySelector(".chip-check")).toBeInTheDocument();
    expect(screen.getByText(/in 1:23/)).toBeInTheDocument();
  });

  it("renders error message when failed", () => {
    render(
      <ActivityChip
        job={makeJob({ status: "failed", errorMessage: "No API key", progressLabel: null })}
      />,
    );

    const chip = screen.getByTestId("bn-activity-chip");
    expect(chip).toHaveAttribute("data-status", "failed");
    expect(chip.querySelector(".chip-error")).toBeInTheDocument();
    expect(screen.getByText(/failed: No API key/)).toBeInTheDocument();
  });

  it("renders close button when completed and fires onDismiss", () => {
    const onDismiss = vi.fn();
    render(
      <ActivityChip
        job={makeJob({ status: "completed", durationLabel: "1:23" })}
        onDismiss={onDismiss}
      />,
    );

    const btn = screen.getByTestId("bn-activity-chip-close");
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("renders close button when failed and fires onDismiss", () => {
    const onDismiss = vi.fn();
    render(
      <ActivityChip
        job={makeJob({ status: "failed", errorMessage: "Timeout" })}
        onDismiss={onDismiss}
      />,
    );

    const btn = screen.getByTestId("bn-activity-chip-close");
    expect(btn).toBeInTheDocument();
    fireEvent.click(btn);
    expect(onDismiss).toHaveBeenCalledOnce();
  });

  it("renders action link when completed and fires onAction", () => {
    const onAction = vi.fn();
    render(
      <ActivityChip
        job={makeJob({ status: "completed", durationLabel: "0:45" })}
        onAction={onAction}
        actionLabel="Report"
      />,
    );

    const link = screen.getByTestId("bn-activity-chip-action");
    expect(link).toHaveTextContent("Report");
    fireEvent.click(link);
    expect(onAction).toHaveBeenCalledOnce();
  });

  it("does not render action link while running", () => {
    render(
      <ActivityChip
        job={makeJob()}
        onAction={vi.fn()}
        actionLabel="Report"
      />,
    );

    expect(screen.queryByTestId("bn-activity-chip-action")).not.toBeInTheDocument();
  });

  it("does not render action link when failed", () => {
    render(
      <ActivityChip
        job={makeJob({ status: "failed", errorMessage: "err" })}
        onAction={vi.fn()}
        actionLabel="Report"
      />,
    );

    expect(screen.queryByTestId("bn-activity-chip-action")).not.toBeInTheDocument();
  });
});
