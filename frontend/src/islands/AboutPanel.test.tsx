import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AboutPanel } from "./AboutPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Mock fetch that routes by URL — returns health for /api/health, 404 for /api/dev/info. */
function mockFetchWithHealth(version: string) {
  vi.spyOn(globalThis, "fetch").mockImplementation((input: RequestInfo | URL) => {
    const url = typeof input === "string" ? input : input.toString();
    if (url.includes("/api/health")) {
      return Promise.resolve(
        new Response(JSON.stringify({ status: "ok", version }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    // /api/dev/info and anything else — 404
    return Promise.resolve(new Response("", { status: 404 }));
  });
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AboutPanel", () => {
  it("renders heading and GitHub link", () => {
    mockFetchWithHealth("0.10.3");
    render(<AboutPanel />);
    expect(screen.getByText("About Bristlenose")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
      "href",
      "https://github.com/cassiocassio/bristlenose",
    );
  });

  it("displays version from /api/health", async () => {
    mockFetchWithHealth("1.2.3");
    render(<AboutPanel />);

    await waitFor(() => {
      expect(screen.getByText(/Version 1\.2\.3/)).toBeInTheDocument();
    });
  });

  it("renders keyboard shortcuts sections", () => {
    mockFetchWithHealth("0.10.3");
    render(<AboutPanel />);

    expect(screen.getByText("Keyboard Shortcuts")).toBeInTheDocument();
    expect(screen.getByText("Navigation")).toBeInTheDocument();
    expect(screen.getByText("Selection")).toBeInTheDocument();
    expect(screen.getByText("Actions")).toBeInTheDocument();
    expect(screen.getByText("Global")).toBeInTheDocument();
  });

  it("renders shortcut descriptions", () => {
    mockFetchWithHealth("0.10.3");
    render(<AboutPanel />);

    expect(screen.getByText("Next quote")).toBeInTheDocument();
    expect(screen.getByText("Star quote(s)")).toBeInTheDocument();
    expect(screen.getByText("Search")).toBeInTheDocument();
  });

  it("renders feedback link", () => {
    mockFetchWithHealth("0.10.3");
    render(<AboutPanel />);

    expect(screen.getByRole("link", { name: "Report a bug" })).toHaveAttribute(
      "href",
      "https://github.com/cassiocassio/bristlenose/issues/new",
    );
  });

  it("handles API error gracefully (no version shown)", () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network error"));
    render(<AboutPanel />);

    // Should still render the heading even without version
    expect(screen.getByText("About Bristlenose")).toBeInTheDocument();
    // Feedback link should still be present
    expect(screen.getByRole("link", { name: "Report a bug" })).toBeInTheDocument();
  });
});
