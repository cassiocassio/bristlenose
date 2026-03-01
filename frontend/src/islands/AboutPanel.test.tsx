import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { AboutPanel } from "./AboutPanel";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(version: string, devInfo: boolean = false) {
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
    if (url.includes("/api/dev/info") && devInfo) {
      return Promise.resolve(
        new Response(
          JSON.stringify({
            db_path: "/tmp/test.db",
            table_count: 22,
            endpoints: [
              { label: "API Docs", url: "/api/docs", description: "Swagger UI" },
            ],
            design_sections: [
              {
                heading: "Mockups",
                items: [{ label: "Test Mockup", url: "/mockups/test.html" }],
              },
            ],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        ),
      );
    }
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
  describe("sidebar navigation", () => {
    it("renders About, Signals, Codebook sidebar items", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);

      expect(screen.getByRole("button", { name: "About" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Signals" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Codebook" })).toBeInTheDocument();
    });

    it("shows all five sidebar items", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);

      expect(screen.getByRole("button", { name: "Developer" })).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Design" })).toBeInTheDocument();
    });

    it("switches content when clicking a sidebar item", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);

      // About section is default
      expect(screen.getByText("About Bristlenose")).toBeInTheDocument();

      // Switch to Signals
      fireEvent.click(screen.getByRole("button", { name: "Signals" }));
      expect(screen.getByText("Sentiment signals")).toBeInTheDocument();
      expect(screen.queryByText("About Bristlenose")).not.toBeInTheDocument();

      // Switch to Codebook
      fireEvent.click(screen.getByRole("button", { name: "Codebook" }));
      expect(screen.getByText("Sections and themes")).toBeInTheDocument();
      expect(screen.queryByText("Sentiment signals")).not.toBeInTheDocument();
    });
  });

  describe("About section", () => {
    it("renders heading and GitHub link", () => {
      mockFetch("0.10.3");
      render(<AboutPanel />);

      expect(screen.getByText("About Bristlenose")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "GitHub" })).toHaveAttribute(
        "href",
        "https://github.com/cassiocassio/bristlenose",
      );
    });

    it("displays version from /api/health", async () => {
      mockFetch("1.2.3");
      render(<AboutPanel />);

      await waitFor(() => {
        expect(screen.getByText(/Version 1\.2\.3/)).toBeInTheDocument();
      });
    });

    it("renders per-screen section headings", () => {
      mockFetch("0.10.3");
      render(<AboutPanel />);

      expect(screen.getByText("Input")).toBeInTheDocument();
      expect(screen.getByText("Dashboard")).toBeInTheDocument();
      expect(screen.getByText("Quotes")).toBeInTheDocument();
      expect(screen.getByText("Sessions")).toBeInTheDocument();
      // "Analysis" appears both as a sidebar button label fragment and as an h3
      expect(screen.getByRole("heading", { name: "Analysis" })).toBeInTheDocument();
      expect(screen.getByText("Export")).toBeInTheDocument();
    });

    it("renders keyboard shortcuts link", () => {
      mockFetch("0.10.3");
      render(<AboutPanel />);

      expect(screen.getByRole("link", { name: "Keyboard shortcuts" })).toBeInTheDocument();
    });

    it("renders feedback link", () => {
      mockFetch("0.10.3");
      render(<AboutPanel />);

      expect(screen.getByRole("link", { name: "Report a bug" })).toHaveAttribute(
        "href",
        "https://github.com/cassiocassio/bristlenose/issues/new",
      );
    });

    it("handles API error gracefully", () => {
      vi.spyOn(globalThis, "fetch").mockRejectedValue(new Error("Network error"));
      render(<AboutPanel />);

      expect(screen.getByText("About Bristlenose")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Report a bug" })).toBeInTheDocument();
    });
  });

  describe("Signals section", () => {
    it("renders sentiment and framework signal headings", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Signals" }));

      expect(screen.getByText("Sentiment signals")).toBeInTheDocument();
      expect(screen.getByText("Framework signals")).toBeInTheDocument();
    });

    it("renders sentiment descriptions", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Signals" }));

      expect(screen.getByText(/Frustration/)).toBeInTheDocument();
      expect(screen.getByText(/Confusion/)).toBeInTheDocument();
      expect(screen.getByText(/Delight/)).toBeInTheDocument();
    });

    it("renders academic references", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Signals" }));

      expect(screen.getByText(/Russell, J\. A\./)).toBeInTheDocument();
      expect(screen.getAllByText(/Fogg, B\. J\./).length).toBeGreaterThan(0);
    });
  });

  describe("Codebook section", () => {
    it("renders three main subsections", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Codebook" }));

      expect(screen.getByText("Sections and themes")).toBeInTheDocument();
      expect(screen.getByText("Sentiment tags")).toBeInTheDocument();
      expect(screen.getByText("Framework codebooks")).toBeInTheDocument();
    });

    it("renders framework descriptions", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Codebook" }));

      expect(screen.getAllByText(/Garrett/).length).toBeGreaterThan(0);
      expect(screen.getAllByText(/Norman/).length).toBeGreaterThan(0);
      expect(screen.getByText("Bristlenose UXR Codebook")).toBeInTheDocument();
    });

    it("renders Braun & Clarke reference", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Codebook" }));

      expect(screen.getByText(/Braun, V\., & Clarke, V\./)).toBeInTheDocument();
    });
  });

  describe("Developer section", () => {
    it("renders architecture and stack info without dev mode", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Developer" }));

      expect(screen.getByText("Architecture")).toBeInTheDocument();
      expect(screen.getByText("Stack")).toBeInTheDocument();
      expect(screen.getByText("Contributing")).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Contributing guide" })).toBeInTheDocument();
    });

    it("renders dev tools when dev info available", async () => {
      mockFetch("0.11.1", true);
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Developer" }));

      await waitFor(() => {
        expect(screen.getByText("22 tables")).toBeInTheDocument();
      });
      expect(screen.getByRole("link", { name: "API Docs" })).toBeInTheDocument();
    });
  });

  describe("Design section", () => {
    it("renders design system info without dev mode", () => {
      mockFetch("0.11.1");
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Design" }));

      expect(screen.getByText("Design system")).toBeInTheDocument();
      expect(screen.getByText("Dark mode")).toBeInTheDocument();
      expect(screen.getByText("Component library")).toBeInTheDocument();
      expect(screen.getByText("Typography")).toBeInTheDocument();
    });

    it("renders design mockups when dev info available", async () => {
      mockFetch("0.11.1", true);
      render(<AboutPanel />);
      fireEvent.click(screen.getByRole("button", { name: "Design" }));

      await waitFor(() => {
        expect(screen.getByText("Mockups")).toBeInTheDocument();
      });
      expect(screen.getByRole("link", { name: "Test Mockup" })).toBeInTheDocument();
    });
  });
});
