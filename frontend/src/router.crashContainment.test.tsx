import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState } from "react";
import { createHashRouter, createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";

// R85: a crash in one lens must stay in that lens, and a crash in a sidebar
// must stay in that sidebar. The report around it — the header, nav, footer,
// the other panels — keeps working, and so do the other lenses. These tests
// mount the real route table and AppLayout, with only the Signals lens, the
// Quotes lens and two sidebars swapped for stand-ins that throw on demand.

const boom = vi.hoisted(() => ({
  mode: "none" as "none" | "first-render" | "on-click",
  tagSidebar: false,
  signalsSidebar: false,
  minimap: false,
}));

vi.mock("./pages/QuotesTab", () => ({
  QuotesTab: () => <div data-testid="quotes-lens" />,
}));

vi.mock("./components/TagSidebar", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./components/TagSidebar")>()),
  TagSidebar: function TagSidebar() {
    if (boom.tagSidebar) throw new Error("kaboom-secret-stack-detail");
    return <div data-testid="tag-sidebar-body" />;
  },
}));

vi.mock("./components/Minimap", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./components/Minimap")>()),
  Minimap: function Minimap() {
    if (boom.minimap) throw new Error("kaboom-secret-stack-detail");
    return <div data-testid="minimap" />;
  },
}));

vi.mock("./components/SignalsSidebar", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./components/SignalsSidebar")>()),
  SignalsSidebar: function SignalsSidebar() {
    if (boom.signalsSidebar) throw new Error("kaboom-secret-stack-detail");
    return <div data-testid="signals-sidebar-body" />;
  },
}));

vi.mock("./pages/SignalsTab", () => ({
  SignalsTab: function SignalsTab() {
    const [broken, setBroken] = useState(false);
    if (boom.mode === "first-render" || broken) {
      throw new Error("kaboom-secret-stack-detail");
    }
    return (
      <div data-testid="signals-lens">
        <button type="button" onClick={() => setBroken(true)}>
          break it
        </button>
      </div>
    );
  },
}));

beforeEach(() => {
  boom.mode = "none";
  boom.tagSidebar = false;
  boom.signalsSidebar = false;
  boom.minimap = false;
  (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE = "/api/projects/1";
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
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(JSON.stringify({ quotes: [], sessions: [], tags: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    }),
  );
  // React and React Router both log a caught render error; keep the run quiet.
  vi.spyOn(console, "error").mockImplementation(() => {});
});

afterEach(() => {
  vi.restoreAllMocks();
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
  delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
  _resetEmbeddedCache();
  document.getElementById("bn-app-root")?.remove();
  window.location.hash = "";
});

function renderAt(path: string) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const utils = render(<RouterProvider router={router} />);
  return { router, ...utils };
}

/** The lens area, which must hold the fallback; the chrome sits outside it. */
function lensArea(container: HTMLElement): HTMLElement {
  const main = container.querySelector<HTMLElement>("main.bn-main");
  expect(main).not.toBeNull();
  return main!;
}

function expectContainedFallback(container: HTMLElement) {
  const alert = within(lensArea(container)).getByRole("alert");
  expect(alert).toHaveTextContent(/couldn.t be shown/i);
  expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  expect(screen.queryByText(/kaboom-secret-stack-detail/)).toBeNull();
  // The detail goes to the console for diagnosis, not to the screen.
  expect(console.error).toHaveBeenCalledWith("[RouteError]", expect.any(Error));
}

describe("a crash in one lens", () => {
  it("on first render is contained to the lens; the nav stays", () => {
    boom.mode = "first-render";
    const { container } = renderAt("/report/signals/");
    expectContainedFallback(container);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Quotes" })).toBeInTheDocument();
  });

  it("after an interaction is contained to the lens; the nav stays", async () => {
    const { container } = renderAt("/report/signals/");
    fireEvent.click(await screen.findByRole("button", { name: "break it" }));
    expectContainedFallback(container);
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("leaves the other lenses reachable, and the broken one stays contained on return", async () => {
    boom.mode = "first-render";
    const { container } = renderAt("/report/signals/");
    expectContainedFallback(container);

    fireEvent.click(screen.getByRole("link", { name: "Sessions" }));
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Sessions" }).className).toContain("active"),
    );
    expect(within(lensArea(container)).queryByRole("alert")).toBeNull();

    fireEvent.click(screen.getByRole("link", { name: "Signals" }));
    await waitFor(() => expectContainedFallback(container));
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("recovers when the lens stops throwing and the researcher comes back to it", async () => {
    boom.mode = "first-render";
    const { container } = renderAt("/report/signals/");
    expectContainedFallback(container);
    boom.mode = "none";
    fireEvent.click(screen.getByRole("link", { name: "Sessions" }));
    fireEvent.click(screen.getByRole("link", { name: "Signals" }));
    expect(await screen.findByTestId("signals-lens")).toBeInTheDocument();
    expect(within(lensArea(container)).queryByRole("alert")).toBeNull();
  });

  it("in the Mac app (embedded, no web nav) is contained and the native nav still switches lens", async () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    boom.mode = "first-render";
    const { container, router } = renderAt("/report/signals/");
    expectContainedFallback(container);
    // The Mac sidebar drives the SPA router; here the router is driven directly.
    await act(() => router.navigate("/report/sessions/"));
    expect(within(lensArea(container)).queryByRole("alert")).toBeNull();
  });

  it("under the hash router (the exported report's router) is contained; the nav stays", () => {
    boom.mode = "first-render";
    window.location.hash = "#/report/signals/";
    const router = createHashRouter(routes);
    try {
      const { container } = render(<RouterProvider router={router} />);
      expectContainedFallback(container);
      expect(screen.getByRole("navigation")).toBeInTheDocument();
    } finally {
      // Resetting the hash in afterEach fires popstate; a live router would follow it.
      router.dispose();
    }
  });
});

function expectContainedPanelFallback(panel: Element) {
  const alert = within(panel as HTMLElement).getByRole("alert");
  expect(alert).toHaveTextContent(/sidebar couldn.t be shown/i);
  expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
  expect(screen.queryByText(/kaboom-secret-stack-detail/)).toBeNull();
  expect(console.error).toHaveBeenCalledWith("[PanelError]", expect.any(Error));
}

describe("a crash in one sidebar", () => {
  beforeEach(() => {
    // Real shapes: the catch-all stub has no `sections`, and the real contents
    // list (TocSidebar) would crash on it once its fetch lands, adding a second
    // panel crash to every test here.
    vi.mocked(globalThis.fetch).mockImplementation(async (input) => {
      const url = String(input);
      const body = url.includes("/quotes")
        ? { sections: [], themes: [], total_quotes: 0, total_hidden: 0, total_starred: 0, has_moderator: false }
        : url.includes("/sessions")
          ? { sessions: [] }
          : url.includes("/codebook")
            ? { groups: [], ungrouped: [], all_tag_names: [] }
            : {};
      return new Response(JSON.stringify(body), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    });
    // jsdom has no scrollIntoView; the contents list's scroll spy calls it.
    Element.prototype.scrollIntoView = vi.fn();
  });

  afterEach(() => {
    Reflect.deleteProperty(Element.prototype, "scrollIntoView");
  });

  it("in the tag sidebar is contained to it; the lens and nav stay", () => {
    boom.tagSidebar = true;
    const { container } = renderAt("/report/quotes/");
    expectContainedPanelFallback(container.querySelector(".tag-sidebar")!);
    expect(screen.getByTestId("quotes-lens")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
    expect(container.querySelector(".bn-route-error:not(.bn-panel-error)")).toBeNull();
  });

  it("in a lens's left panel is contained to it; the lens and nav stay", () => {
    boom.signalsSidebar = true;
    const { container } = renderAt("/report/signals/");
    expectContainedPanelFallback(container.querySelector(".toc-sidebar")!);
    expect(screen.getByTestId("signals-lens")).toBeInTheDocument();
    expect(screen.getByRole("navigation")).toBeInTheDocument();
  });

  it("comes back on Retry once it stops throwing", async () => {
    boom.tagSidebar = true;
    const { container } = renderAt("/report/quotes/");
    const panel = container.querySelector(".tag-sidebar")!;
    expectContainedPanelFallback(panel);
    boom.tagSidebar = false;
    fireEvent.click(within(panel as HTMLElement).getByRole("button", { name: "Retry" }));
    expect(await screen.findByTestId("tag-sidebar-body")).toBeInTheDocument();
    expect(within(panel as HTMLElement).queryByRole("alert")).toBeNull();
  });

  it("is cleared by choosing another lens", async () => {
    boom.signalsSidebar = true;
    const { container } = renderAt("/report/signals/");
    expectContainedPanelFallback(container.querySelector(".toc-sidebar")!);
    boom.signalsSidebar = false;
    fireEvent.click(screen.getByRole("link", { name: "Quotes" }));
    fireEvent.click(screen.getByRole("link", { name: "Signals" }));
    expect(await screen.findByTestId("signals-sidebar-body")).toBeInTheDocument();
  });

  it("in the minimap leaves an empty column, not a message, and the rest stays", () => {
    boom.minimap = true;
    const { container } = renderAt("/report/quotes/");
    expect(screen.queryByTestId("minimap")).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.getByTestId("quotes-lens")).toBeInTheDocument();
    expect(within(container.querySelector(".tag-sidebar") as HTMLElement).getByTestId("tag-sidebar-body")).toBeInTheDocument();
    expect(console.error).toHaveBeenCalledWith("[PanelError]", expect.any(Error));
  });
});
