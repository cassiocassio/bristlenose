import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, render } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "../router";
import { _resetEmbeddedCache } from "../utils/embedded";
import { CLASS_QUOTE_EDITS, isQuoteEdits, _resetQuoteEdits } from "../contexts/QuoteEditsStore";

// View ▸ Show / Hide Quote Edits, as AppLayout wires it: the state is posted to the Mac on mount
// and on change, the menu action toggles it only on a transcript, and leaving the transcript clears
// it. The transcript and Quotes pages are stand-ins; the layout and the route table are real.

vi.mock("../pages/TranscriptTab", () => ({
  TranscriptTab: () => <div data-testid="transcript" />,
}));
vi.mock("../pages/QuotesTab", () => ({
  QuotesTab: () => <div data-testid="quotes-lens" />,
}));

let post: ReturnType<typeof vi.fn>;

function quoteEditsPosts(): Array<{ available: boolean; on: boolean }> {
  return post.mock.calls
    .map(([m]) => m as { type: string; available: boolean; on: boolean })
    .filter((m) => m.type === "quote-edits-state")
    .map(({ available, on }) => ({ available, on }));
}

function lastPost() {
  const posts = quoteEditsPosts();
  return posts[posts.length - 1];
}

function menuAction(action: string): void {
  act(() => {
    window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action } }));
  });
}

beforeEach(() => {
  _resetQuoteEdits();
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";
  (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
  _resetEmbeddedCache();
  post = vi.fn();
  (window as unknown as Record<string, unknown>).webkit = { messageHandlers: { navigation: { postMessage: post } } };
  const root = document.createElement("div");
  root.id = "bn-app-root";
  root.setAttribute("data-project-id", "1");
  document.body.appendChild(root);
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })),
  });
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
      new Response(JSON.stringify({ quotes: [], sessions: [], tags: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
  );
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
  delete (window as unknown as Record<string, unknown>).webkit;
  _resetEmbeddedCache();
  _resetQuoteEdits();
  document.getElementById("bn-app-root")?.remove();
});

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  render(<RouterProvider router={router} />);
  return router;
}

describe("AppLayout and View ▸ Show / Hide Quote Edits", () => {
  it("posts 'on a transcript, off' on mount, which is the re-sync after a reload", () => {
    renderAt("/report/sessions/s1");
    expect(quoteEditsPosts()).toContainEqual({ available: true, on: false });
  });

  it("posts 'not available' on a lens that is not a transcript", () => {
    renderAt("/report/quotes/");
    expect(quoteEditsPosts()).toContainEqual({ available: false, on: false });
    expect(quoteEditsPosts().some((p) => p.available)).toBe(false);
  });

  it("toggles on the menu action on a transcript, mirrors it to the Mac and sets the root class", () => {
    renderAt("/report/sessions/s1");
    menuAction("quoteEdits");
    expect(isQuoteEdits()).toBe(true);
    expect(document.documentElement.classList.contains(CLASS_QUOTE_EDITS)).toBe(true);
    expect(lastPost()).toEqual({ available: true, on: true });
    menuAction("quoteEdits");
    expect(isQuoteEdits()).toBe(false);
    expect(lastPost()).toEqual({ available: true, on: false });
  });

  it("ignores a stray menu action off the transcript", () => {
    renderAt("/report/quotes/");
    menuAction("quoteEdits");
    expect(isQuoteEdits()).toBe(false);
    expect(document.documentElement.classList.contains(CLASS_QUOTE_EDITS)).toBe(false);
  });

  it("clears the state on leaving the transcript, so the tick and the class never outlive the page", async () => {
    const router = renderAt("/report/sessions/s1");
    menuAction("quoteEdits");
    expect(isQuoteEdits()).toBe(true);
    await act(async () => {
      await router.navigate("/report/quotes/");
    });
    expect(isQuoteEdits()).toBe(false);
    expect(document.documentElement.classList.contains(CLASS_QUOTE_EDITS)).toBe(false);
    expect(lastPost()).toEqual({ available: false, on: false });
    // And the Mac never hears "unavailable, on" in between: `on` is only reported with `available`.
    expect(quoteEditsPosts()).not.toContainEqual({ available: false, on: true });
  });

  it("stays on when moving from one transcript to another (compare quotes across sessions)", async () => {
    const router = renderAt("/report/sessions/s1");
    menuAction("quoteEdits");
    await act(async () => {
      await router.navigate("/report/sessions/s2");
    });
    expect(isQuoteEdits()).toBe(true);
    expect(lastPost()).toEqual({ available: true, on: true });
  });
});
