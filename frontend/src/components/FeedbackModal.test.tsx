import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { FeedbackModal } from "./FeedbackModal";
import type { HealthResponse } from "../utils/health";
import { toast } from "../utils/toast";

vi.mock("../utils/toast", () => ({ toast: vi.fn() }));

const HEALTH: HealthResponse = {
  status: "ok",
  version: "9.9.9",
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

describe("FeedbackModal", () => {
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    localStorage.clear();
    vi.mocked(toast).mockReset();
  });

  it("renders hidden overlay when open is false", () => {
    render(<FeedbackModal open={false} onClose={vi.fn()} health={HEALTH} />);
    const overlay = screen.getByTestId("bn-feedback-overlay");
    expect(overlay).toHaveAttribute("aria-hidden", "true");
    expect(overlay.className).not.toContain("visible");
  });

  it("disables send until sentiment is selected", () => {
    render(<FeedbackModal open={true} onClose={vi.fn()} health={HEALTH} />);
    const send = screen.getByRole("button", { name: "Send" }) as HTMLButtonElement;
    expect(send.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    expect(send.disabled).toBe(false);
  });

  it("restores draft from localStorage and autosaves changes", async () => {
    localStorage.setItem(
      "bristlenose-feedback-draft",
      JSON.stringify({ rating: "like", message: "Existing draft" }),
    );
    render(<FeedbackModal open={true} onClose={vi.fn()} health={HEALTH} />);

    const textarea = screen.getByLabelText("Help us improve") as HTMLTextAreaElement;
    expect(textarea.value).toBe("Existing draft");
    expect(screen.getByRole("button", { name: /Good/ }).className).toContain("selected");

    fireEvent.change(textarea, { target: { value: "Updated draft text" } });
    fireEvent.click(screen.getByRole("button", { name: /Excellent/ }));

    await waitFor(() => {
      const saved = localStorage.getItem("bristlenose-feedback-draft");
      expect(saved).toBeTruthy();
      const parsed = JSON.parse(saved || "{}");
      expect(parsed.message).toBe("Updated draft text");
      expect(parsed.rating).toBe("love");
    });
  });

  it("posts feedback to endpoint on success", async () => {
    const onClose = vi.fn();
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("{}", { status: 200 }),
    );
    render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);

    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.change(screen.getByLabelText("Help us improve"), {
      target: { value: "Works well." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(fetchSpy).toHaveBeenCalledOnce();
      expect(fetchSpy).toHaveBeenCalledWith(
        "https://example.com/feedback",
        expect.objectContaining({
          method: "POST",
          headers: { "Content-Type": "application/json" },
        }),
      );
      expect(onClose).toHaveBeenCalledOnce();
      expect(vi.mocked(toast)).toHaveBeenCalledWith("Feedback sent - thank you!");
    });
  });

  it("falls back to clipboard when POST fails", async () => {
    const onClose = vi.fn();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network"));
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);

    fireEvent.click(screen.getByRole("button", { name: /Needs work/ }));
    fireEvent.change(screen.getByLabelText("Help us improve"), {
      target: { value: "Something failed." },
    });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledOnce();
      expect(onClose).toHaveBeenCalledOnce();
      expect(vi.mocked(toast)).toHaveBeenCalledWith(
        "Copied to clipboard - paste into an email or issue.",
      );
    });
  });

  it("closes on Escape and overlay click", () => {
    const onClose = vi.fn();
    render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    const overlay = screen.getByTestId("bn-feedback-overlay");
    fireEvent.click(overlay);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
