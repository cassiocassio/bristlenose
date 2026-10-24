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
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
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
      expect(vi.mocked(toast)).toHaveBeenCalledWith("Feedback sent — thank you!");
    });
  });

  it("falls back to clipboard on a 200 without {ok:true} (captive-portal / proxy interstitial)", async () => {
    // A hotel/proxy interstitial returns HTTP 200 with an HTML body; feedback.php
    // never saw the payload. A bare resp.ok would toast "sent" and drop it — the
    // strict predicate must treat this as a failure and preserve the message.
    const onClose = vi.fn();
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>Please sign in to the WiFi</html>", {
        status: 200,
        headers: { "Content-Type": "text/html" },
      }),
    );
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText },
      configurable: true,
    });

    render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    await waitFor(() => {
      expect(writeText).toHaveBeenCalledOnce();
      expect(screen.getByRole("alert").textContent).toContain("Couldn’t send your feedback.");
    });
    expect(onClose).not.toHaveBeenCalled();
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

    // R80: the form says the send failed and where to paste the copy, and
    // keeps the text; it does not close behind a "Copied to clipboard" toast.
    const alert = await screen.findByRole("alert");
    expect(writeText).toHaveBeenCalledOnce();
    expect(alert.textContent).toContain(
      "Couldn’t send your feedback. It’s copied to the clipboard: paste it into a new issue on GitHub.",
    );
    const link = screen.getByRole("link", { name: "Report an issue" });
    expect(link.getAttribute("href")).toBe("https://example.com/issues/new");
    expect(link.getAttribute("target")).toBe("_blank");
    expect(onClose).not.toHaveBeenCalled();
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
    expect((screen.getByLabelText("Help us improve") as HTMLTextAreaElement).value).toBe(
      "Something failed.",
    );
    expect((screen.getByRole("button", { name: "Send" }) as HTMLButtonElement).disabled).toBe(false);
    const saved = JSON.parse(localStorage.getItem("bristlenose-feedback-draft") || "{}");
    expect(saved.message).toBe("Something failed.");
  });

  it("clears the failure when the form is sent again and when it is reopened", async () => {
    const onClose = vi.fn();
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network"));
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });

    const { rerender } = render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("alert");

    // Sending again: the old sentence goes as the new send starts.
    let release!: (r: Response) => void;
    vi.mocked(globalThis.fetch).mockImplementationOnce(
      () => new Promise<Response>((resolve) => { release = resolve; }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByRole("button", { name: "Sending…" })).toBeDefined();
    release(new Response("{}", { status: 500 }));
    await screen.findByRole("alert");

    rerender(<FeedbackModal open={false} onClose={onClose} health={HEALTH} />);
    rerender(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
    expect(screen.queryByRole("alert")).toBeNull();
  });

  it.each([
    ["rejects", () => ({ writeText: vi.fn().mockRejectedValue(new Error("denied")) })],
    ["is unavailable", () => undefined],
  ])(
    "keeps the text in the form when the send fails and the clipboard %s",
    async (_label, clipboard) => {
      const onClose = vi.fn();
      const fetchSpy = vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network"));
      Object.defineProperty(navigator, "clipboard", {
        value: clipboard(),
        configurable: true,
      });

      render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
      fireEvent.click(screen.getByRole("button", { name: /Needs work/ }));
      const textarea = screen.getByLabelText("Help us improve") as HTMLTextAreaElement;
      fireEvent.change(textarea, { target: { value: "Long careful feedback." } });
      const send = screen.getByRole("button", { name: "Send" }) as HTMLButtonElement;
      fireEvent.click(send);

      const alert = await screen.findByRole("alert");
      expect(alert.textContent).toContain(
        "Couldn’t send your feedback or copy it to the clipboard.",
      );
      expect(vi.mocked(toast)).not.toHaveBeenCalled();
      expect(fetchSpy).toHaveBeenCalledOnce();
      expect(onClose).not.toHaveBeenCalled();
      expect(textarea.value).toBe("Long careful feedback.");
      expect(screen.getByRole("button", { name: /Needs work/ }).className).toContain("selected");
      expect(send.disabled).toBe(false);
      const saved = JSON.parse(localStorage.getItem("bristlenose-feedback-draft") || "{}");
      expect(saved.message).toBe("Long careful feedback.");
    },
  );

  it("with no endpoint, sends nothing and says so in the form", async () => {
    // The no-endpoint branch (an empty feedback URL; a file:// page takes the
    // same branch): no POST, the copy, and the failure line. Same as the Mac.
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const health = { ...HEALTH, feedback: { enabled: true, url: "" } };

    render(<FeedbackModal open={true} onClose={vi.fn()} health={health} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toContain("Couldn\u2019t send your feedback.");
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(writeText).toHaveBeenCalledOnce();
  });

  it("an edit after a failure takes the failure line away", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network"));
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      configurable: true,
    });
    render(<FeedbackModal open={true} onClose={vi.fn()} health={HEALTH} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("alert");

    fireEvent.change(screen.getByLabelText("Help us improve"), { target: { value: "More." } });
    expect(screen.queryByRole("alert")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("alert");
    fireEvent.click(screen.getByRole("button", { name: /Excellent/ }));
    expect(screen.queryByRole("alert")).toBeNull();
  });

  /** A POST the test answers by hand, after the form has been closed. */
  function heldFetch(): (r: Response | Error) => void {
    let settle!: (r: Response | Error) => void;
    vi.spyOn(globalThis, "fetch").mockImplementation(
      (_url, init) =>
        new Promise<Response>((resolve, reject) => {
          settle = (r) => (r instanceof Error ? reject(r) : resolve(r));
          // A real fetch rejects on abort; this one only does when answered,
          // so the guard is tested against a request the server already had.
          void init;
        }),
    );
    return (r) => settle(r);
  }

  const closers: [string, () => void][] = [
    ["Cancel", () => fireEvent.click(screen.getByRole("button", { name: "Cancel" }))],
    ["Escape", () => fireEvent.keyDown(document, { key: "Escape" })],
    ["the close button", () => fireEvent.click(screen.getByRole("button", { name: "Close" }))],
  ];
  const failures: [string, () => Response | Error][] = [
    ["a network error", () => new Error("network")],
    ["a 500", () => new Response("{}", { status: 500 })],
  ];

  it.each(closers.flatMap(([c, closeIt]) => failures.map(([f, failure]) => [c, f, closeIt, failure] as const)))(
    "closed with %s during a send that then ends in %s, writes nothing",
    async (_c, _f, closeIt, failure) => {
    const onClose = vi.fn();
    const answer = heldFetch();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    closeIt();
    answer(failure());
    await new Promise((r) => setTimeout(r, 0));

    expect(onClose).toHaveBeenCalledOnce();
    expect(writeText).not.toHaveBeenCalled();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
  });

  it("closed while the copy is being written, shows no failure line", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("network"));
    let copied!: () => void;
    const writeText = vi.fn(() => new Promise<void>((r) => { copied = r; }));
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    render(<FeedbackModal open={true} onClose={vi.fn()} health={HEALTH} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    await waitFor(() => expect(writeText).toHaveBeenCalledOnce());
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    copied();
    await new Promise((r) => setTimeout(r, 0));

    expect(screen.queryByRole("alert")).toBeNull();
  });

  it("closed during a send that then succeeds, does not close again or wipe the draft", async () => {
    const onClose = vi.fn();
    const answer = heldFetch();

    render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.change(screen.getByLabelText("Help us improve"), { target: { value: "Keep me." } });
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    answer(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    await new Promise((r) => setTimeout(r, 0));

    expect(onClose).toHaveBeenCalledOnce();
    expect(vi.mocked(toast)).not.toHaveBeenCalled();
    const saved = JSON.parse(localStorage.getItem("bristlenose-feedback-draft") || "{}");
    expect(saved.message).toBe("Keep me.");
  });

  it("closed from outside during a send, writes nothing when it fails", async () => {
    const answer = heldFetch();
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const { rerender } = render(<FeedbackModal open={true} onClose={vi.fn()} health={HEALTH} />);
    fireEvent.click(screen.getByRole("button", { name: /Good/ }));
    fireEvent.click(screen.getByRole("button", { name: "Send" }));
    rerender(<FeedbackModal open={false} onClose={vi.fn()} health={HEALTH} />);
    answer(new Error("network"));
    await new Promise((r) => setTimeout(r, 0));

    expect(writeText).not.toHaveBeenCalled();
    // Reopened, Send is not left reading "Sending…".
    rerender(<FeedbackModal open={true} onClose={vi.fn()} health={HEALTH} />);
    const send = screen.getByRole("button", { name: "Send" }) as HTMLButtonElement;
    expect(send.disabled).toBe(false);
  });

  it("closes on Escape and the close button, never on a click on the backdrop", () => {
    const onClose = vi.fn();
    render(<FeedbackModal open={true} onClose={onClose} health={HEALTH} />);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    expect(onClose).toHaveBeenCalledTimes(2);

    fireEvent.click(screen.getByTestId("bn-feedback-overlay"));
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
