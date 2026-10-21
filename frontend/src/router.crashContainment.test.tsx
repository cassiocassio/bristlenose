import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { useState, type ReactNode } from "react";
import { createHashRouter, createMemoryRouter, RouterProvider } from "react-router-dom";
import { routes } from "./router";
import { _resetEmbeddedCache } from "./utils/embedded";
import { featureFlags } from "./utils/featureFlags";
import { postReportError } from "./shims/bridge";

const mockPostReportError = vi.mocked(postReportError);

// R85: a crash in one lens must stay in that lens, a crash in a sidebar must
// stay in that sidebar, and a crash in the chrome (header, nav, footer, the
// activity chips, a modal) must stay in that part. The rest of the report
// keeps working, and so do the other lenses. These tests mount the real route
// table and AppLayout, with the Signals and Quotes lenses swapped for stand-ins
// and the sidebars and chrome wrapped to throw on demand; a modal's content
// throws through `t()` on a key only it reads.

const boom = vi.hoisted(() => ({
  mode: "none" as "none" | "first-render" | "on-click",
  tagSidebar: false,
  signalsSidebar: false,
  minimap: false,
  // The layout itself: a throw here climbs to the /report boundary, the
  // whole-report crash (decision #2).
  layout: false,
  // The chrome AppLayout mounts beside the lens (decision #9).
  header: false,
  navBar: false,
  footer: false,
  chips: false,
  announce: false,
  subtitle: false,
  undo: false,
  search: false,
  // A modal's content throws through the one translation it alone reads, so the
  // throw happens inside that modal's content and nowhere else.
  tKey: null as string | null,
}));

function throwsWhen<P extends object>(flag: () => boolean, Real: (props: P) => ReactNode) {
  return function Stand(props: P) {
    if (flag()) throw new Error("kaboom-secret-stack-detail");
    return <Real {...props} />;
  };
}

vi.mock("react-i18next", async (importOriginal) => {
  const real = await importOriginal<typeof import("react-i18next")>();
  return {
    ...real,
    useTranslation: ((...args: Parameters<typeof real.useTranslation>) => {
      const r = real.useTranslation(...args);
      if (!boom.tKey) return r;
      const realT = r.t as unknown as (...a: unknown[]) => string;
      const t = ((key: string, ...rest: unknown[]) => {
        if (key === boom.tKey) throw new Error("kaboom-secret-stack-detail");
        return realT(key, ...rest);
      }) as unknown as typeof r.t;
      return { ...r, t };
    }) as typeof real.useTranslation,
  };
});

// The shell's end of the whole-report crash: `report-error` is posted for
// the /report boundary and never for a lens (`postReportError`); the real
// poster no-ops outside WKWebView, so a stub is the only way to see it.
vi.mock("./shims/bridge", async (importOriginal) => ({
  ...(await importOriginal<typeof import("./shims/bridge")>()),
  postReportError: vi.fn(),
}));

vi.mock("./layouts/AppLayout", async (importOriginal) => {
  const real = await importOriginal<typeof import("./layouts/AppLayout")>();
  return { ...real, AppLayout: throwsWhen(() => boom.layout, real.AppLayout) };
});

vi.mock("./components/Header", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/Header")>();
  return { ...real, Header: throwsWhen(() => boom.header, real.Header) };
});

vi.mock("./components/NavBar", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/NavBar")>();
  return { ...real, NavBar: throwsWhen(() => boom.navBar, real.NavBar) };
});

vi.mock("./components/Footer", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/Footer")>();
  return { ...real, Footer: throwsWhen(() => boom.footer, real.Footer) };
});

vi.mock("./components/ActivityChipStack", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/ActivityChipStack")>();
  return { ...real, ActivityChipStack: throwsWhen(() => boom.chips, real.ActivityChipStack) };
});

vi.mock("./components/AnnounceRegion", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/AnnounceRegion")>();
  return { ...real, AnnounceRegion: throwsWhen(() => boom.announce, real.AnnounceRegion) };
});

vi.mock("./components/LensSubtitleSync", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/LensSubtitleSync")>();
  return { ...real, LensSubtitleSync: throwsWhen(() => boom.subtitle, real.LensSubtitleSync) };
});

vi.mock("./components/UndoSync", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/UndoSync")>();
  return { ...real, UndoSync: throwsWhen(() => boom.undo, real.UndoSync) };
});

vi.mock("./components/NativeSearchSync", async (importOriginal) => {
  const real = await importOriginal<typeof import("./components/NativeSearchSync")>();
  return { ...real, NativeSearchSync: throwsWhen(() => boom.search, real.NativeSearchSync) };
});

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
  boom.layout = false;
  mockPostReportError.mockClear();
  boom.header = false;
  boom.navBar = false;
  boom.footer = false;
  boom.chips = false;
  boom.announce = false;
  boom.subtitle = false;
  boom.undo = false;
  boom.search = false;
  boom.tKey = null;
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
  // A fresh Response per call: one shared Response's body reads once, so every
  // later read failed, and the Sessions lens showed its read-failed notice (an
  // alert since R86) where these tests look for no alert.
  vi.spyOn(globalThis, "fetch").mockImplementation(
    async () =>
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

describe("a crash in the whole report", () => {
  // Decision #2 (21 Oct 2026, spec docs/mockups/report-crash-fallback.html):
  // the /report boundary says what couldn't be shown, keeps Retry, and tells
  // the shell once — route, error, first frames — so the Mac sidebar row and
  // its popover have something to show. A lens crash tells the shell nothing.

  it("says the report couldn't be shown, with Retry, and nothing of the error", () => {
    boom.layout = true;
    renderAt("/report/quotes/");
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent("This report couldn’t be shown.");
    expect(alert).not.toHaveTextContent(/^Error$/);
    expect(within(alert).getByRole("button", { name: "Retry" })).toBeInTheDocument();
    expect(screen.queryByText(/kaboom-secret-stack-detail/)).toBeNull();
    expect(screen.queryByRole("navigation")).toBeNull();
    expect(console.error).toHaveBeenCalledWith("[RouteError]", expect.any(Error));
  });

  it("posts report-error to the shell once, with the route, the error and bounded frames", () => {
    boom.layout = true;
    renderAt("/report/quotes/");
    expect(mockPostReportError).toHaveBeenCalledOnce();
    const [route, message, frames] = mockPostReportError.mock.calls[0];
    expect(route).toBe("/report/quotes/");
    expect(message).toBe("Error: kaboom-secret-stack-detail");
    expect(frames.length).toBeGreaterThan(0);
    expect(frames.length).toBeLessThanOrEqual(8);
    // Frames, not the message line repeated: V8's `at …` or JSC's `fn@url`.
    for (const f of frames) expect(f).toMatch(/^at |@/);
    expect(frames.join("\n")).not.toContain("kaboom-secret-stack-detail");
  });

  it("posts once per crash: a navigation that crashes again posts again", async () => {
    boom.layout = true;
    const { router } = renderAt("/report/quotes/");
    expect(mockPostReportError).toHaveBeenCalledOnce();
    // The boundary resets on navigation, the layout throws again: a second
    // crash, a second post. The fallback re-rendering in between posts nothing
    // (the effect is keyed on the error object).
    await act(async () => {
      await router.navigate("/report/sessions/");
    });
    expect(mockPostReportError).toHaveBeenCalledTimes(2);
    expect(mockPostReportError.mock.calls[1][0]).toBe("/report/sessions/");
  });

  it("for a lens crash tells the shell nothing", () => {
    boom.mode = "first-render";
    const { container } = renderAt("/report/signals/");
    expectContainedFallback(container);
    expect(mockPostReportError).not.toHaveBeenCalled();
  });

  it("for a sidebar or chrome crash tells the shell nothing", () => {
    boom.navBar = true;
    boom.tagSidebar = true;
    renderAt("/report/quotes/");
    expect(screen.getByTestId("quotes-lens")).toBeInTheDocument();
    expect(mockPostReportError).not.toHaveBeenCalled();
  });
});

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

// Decision #9: the chrome around the lens. Header and nav show the broken mark
// in their own slot; footer, activity chips and the invisible syncs draw
// nothing; a modal shows the mark inside its own box, and can still be closed.

/** The part fallback: the broken mark alone, named for assistive technology,
 *  with no words on screen, no button and no alert (owner, 20 Oct 2026). */
function expectPartFallback(slot: Element) {
  const fallback = (slot as HTMLElement).querySelector<HTMLElement>(".bn-part-error");
  expect(fallback).not.toBeNull();
  expect(fallback).toHaveClass("bn-route-error");
  expect(within(fallback!).getByRole("img", { name: "This couldn’t be shown." })).toBeInTheDocument();
  expect(fallback!.textContent).toBe("");
  expect(within(fallback!).queryByRole("button")).toBeNull();
  expect(within(slot as HTMLElement).queryByRole("alert")).toBeNull();
  expect(screen.queryByText(/kaboom-secret-stack-detail/)).toBeNull();
  expect(console.error).toHaveBeenCalledWith("[PanelError]", expect.any(Error));
}

/** The whole-report fallback (the /report errorElement) is not on screen. */
function expectReportStands(container: HTMLElement) {
  expect(container.querySelector(".bn-route-error:not(.bn-panel-error):not(.bn-part-error)")).toBeNull();
  expect(screen.getByTestId("signals-lens")).toBeInTheDocument();
}

/** A bar's fallback sits in the bar's own slot, a direct child of the centre column. */
function barFallbacks(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(".center > .bn-part-error"));
}

describe("a crash in the chrome around the lens", () => {
  it("in the nav shows the part fallback in the nav's slot; header, lens and footer stay", () => {
    boom.navBar = true;
    const { container } = renderAt("/report/signals/");
    const slots = barFallbacks(container);
    expect(slots).toHaveLength(1);
    expectPartFallback(container.querySelector(".center")!);
    expectReportStands(container);
    // The nav's slot, not the header's: the header is drawn, and the fallback follows it.
    const header = container.querySelector(".report-header")!;
    expect(header).not.toBeNull();
    expect(header.compareDocumentPosition(slots[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Quotes" })).toBeNull();
    expect(screen.getByRole("button", { name: "Feedback" })).toBeInTheDocument();
  });

  it("in the header shows the part fallback in the header's slot; nav and lens stay", () => {
    boom.header = true;
    const { container } = renderAt("/report/signals/");
    const slots = barFallbacks(container);
    expect(slots).toHaveLength(1);
    expectPartFallback(container.querySelector(".center")!);
    expectReportStands(container);
    // The header's slot, not the nav's: the nav is drawn, and the fallback precedes it.
    expect(container.querySelector(".report-header")).toBeNull();
    const quotes = screen.getByRole("link", { name: "Quotes" });
    expect(slots[0].compareDocumentPosition(quotes) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("in the footer draws nothing, and the rest stays", () => {
    boom.footer = true;
    const { container } = renderAt("/report/signals/");
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByRole("button", { name: "Feedback" })).toBeNull();
    expectReportStands(container);
    expect(screen.getByRole("link", { name: "Quotes" })).toBeInTheDocument();
    expect(console.error).toHaveBeenCalledWith("[PanelError]", expect.any(Error));
  });

  it("in the activity chips draws nothing, and the rest stays", () => {
    boom.chips = true;
    const { container } = renderAt("/report/signals/");
    expect(screen.queryByRole("alert")).toBeNull();
    expectReportStands(container);
    expect(screen.getByRole("link", { name: "Quotes" })).toBeInTheDocument();
    expect(console.error).toHaveBeenCalledWith("[PanelError]", expect.any(Error));
  });

  for (const [name, flag] of [
    ["the announcer", "announce"],
    ["the lens subtitle sync", "subtitle"],
    ["the undo sync", "undo"],
    ["the native search sync", "search"],
  ] as const) {
    it(`in ${name} (invisible) draws nothing, and the rest stays`, () => {
      boom[flag] = true;
      const { container } = renderAt("/report/signals/");
      expect(screen.queryByRole("alert")).toBeNull();
      expectReportStands(container);
      expect(screen.getByRole("link", { name: "Quotes" })).toBeInTheDocument();
      expect(console.error).toHaveBeenCalledWith("[PanelError]", expect.any(Error));
    });
  }

  it("is cleared by a route change", async () => {
    boom.navBar = true;
    const { container, router } = renderAt("/report/signals/");
    expectPartFallback(container.querySelector(".center")!);
    boom.navBar = false;
    await act(() => router.navigate("/report/sessions/"));
    expect(await screen.findByRole("link", { name: "Quotes" })).toBeInTheDocument();
    expect(barFallbacks(container)).toHaveLength(0);
  });
});

describe("a crash inside an open modal", () => {
  afterEach(() => {
    featureFlags.figjamExport = false;
  });

  /** Open it, with its content throwing; the fallback must sit inside its .bn-modal. */
  async function openBroken(key: string, open: () => unknown, testId: string) {
    const utils = renderAt("/report/signals/");
    // Broken from the moment it opens, not at mount: every modal is mounted
    // closed, so a throw set before the render would happen with it shut.
    boom.tKey = key;
    await open();
    const overlay = await screen.findByTestId(testId);
    expect(overlay).toHaveClass("visible");
    const modal = overlay.querySelector(".bn-modal");
    expect(modal).not.toBeNull();
    expectPartFallback(modal!);
    expectReportStands(utils.container);
    return { ...utils, overlay };
  }

  async function exportMenu(item: RegExp) {
    fireEvent.click(screen.getByRole("button", { name: "Export" }));
    fireEvent.click(await screen.findByRole("menuitem", { name: item }));
  }

  const cases: { name: string; key: string; testId: string; open: () => unknown; flag?: boolean }[] = [
    { name: "Send to Miro", key: "miro.title", testId: "bn-miro-overlay", open: () => exportMenu(/Send to Miro/) },
    { name: "Export Report", key: "export.heading", testId: "bn-export-overlay", open: () => exportMenu(/Export Report/) },
    {
      name: "Feedback",
      key: "feedback.heading",
      testId: "bn-feedback-overlay",
      open: () => fireEvent.click(screen.getByRole("button", { name: "Feedback" })),
    },
    {
      name: "Send to FigJam",
      key: "figjam.title",
      testId: "bn-figjam-overlay",
      flag: true,
      open: () => exportMenu(/Send to FigJam/),
    },
    {
      name: "Settings",
      key: "appearance.legend",
      testId: "bn-settings-overlay",
      open: () => fireEvent.click(screen.getByRole("button", { name: "Settings" })),
    },
  ];

  for (const c of cases) {
    it(`${c.name}: contained in the modal, and Escape still closes it`, async () => {
      if (c.flag) featureFlags.figjamExport = true;
      const { overlay } = await openBroken(c.key, c.open, c.testId);
      fireEvent.keyDown(document, { key: "Escape" });
      await waitFor(() => expect(overlay).not.toHaveClass("visible"));
      expectReportStands(document.body);
    });

    it(`${c.name}: contained in the modal, and a click outside still closes it`, async () => {
      if (c.flag) featureFlags.figjamExport = true;
      const { overlay } = await openBroken(c.key, c.open, c.testId);
      fireEvent.click(overlay);
      await waitFor(() => expect(overlay).not.toHaveClass("visible"));
    });
  }

  it("that throws from the start leaves the report standing at load, and shows the fallback when opened", async () => {
    // Every modal is mounted closed, so a throw that does not depend on being
    // open happens when the report loads, before anyone asks for the modal.
    boom.tKey = "miro.title";
    const { container } = renderAt("/report/signals/");
    expectReportStands(container);
    expect(screen.getByRole("link", { name: "Quotes" })).toBeInTheDocument();
    await exportMenu(/Send to Miro/);
    const overlay = await screen.findByTestId("bn-miro-overlay");
    expect(overlay).toHaveClass("visible");
    expectPartFallback(overlay.querySelector(".bn-modal")!);
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(overlay).not.toHaveClass("visible"));
  });

  // F1: these two dialogs are named by their heading (aria-labelledby), and the
  // heading is content, so it goes with a crash. The mark then names the dialog
  // and takes the focus the heading would have had.
  for (const c of [
    { name: "Send to Miro", key: "miro.title", testId: "bn-miro-overlay", menu: /Send to Miro/, flag: false },
    { name: "Send to FigJam", key: "figjam.title", testId: "bn-figjam-overlay", menu: /Send to FigJam/, flag: true },
  ]) {
    it(`${c.name}: a crashed dialog is named by the mark, which takes the focus`, async () => {
      if (c.flag) featureFlags.figjamExport = true;
      const { overlay } = await openBroken(c.key, () => exportMenu(c.menu), c.testId);
      const dialog = within(overlay).getByRole("dialog", { name: "This couldn’t be shown." });
      const mark = dialog.querySelector(".bn-part-error");
      await waitFor(() => expect(document.activeElement).toBe(mark));
    });
  }

  it("Settings: the × still closes it, and another section still opens", async () => {
    const { overlay } = await openBroken(
      "appearance.legend",
      () => fireEvent.click(screen.getByRole("button", { name: "Settings" })),
      "bn-settings-overlay",
    );
    const modal = overlay.querySelector(".bn-modal") as HTMLElement;
    // Another section clears it, the way another lens clears a lens crash.
    fireEvent.click(within(modal).getByRole("button", { name: "Pipeline" }));
    await waitFor(() => expect(modal.querySelector(".bn-part-error")).toBeNull());
    fireEvent.click(within(modal).getByRole("button", { name: "Close" }));
    await waitFor(() => expect(overlay).not.toHaveClass("visible"));
  });

  it("comes back after a route change once it stops throwing", async () => {
    const { overlay, router } = await openBroken("export.heading", () => exportMenu(/Export Report/), "bn-export-overlay");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(overlay).not.toHaveClass("visible"));
    boom.tKey = null;
    await act(() => router.navigate("/report/sessions/"));
    await exportMenu(/Export Report/);
    expect(await within(overlay).findByRole("heading", { name: "Export report" })).toBeInTheDocument();
    expect(overlay.querySelector(".bn-part-error")).toBeNull();
  });

  it("in the Mac app (opened from the menu) is contained in the modal, and Escape closes it", async () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    const { overlay } = await openBroken("feedback.heading", () => {
      act(() => {
        window.dispatchEvent(new CustomEvent("bn:menu-action", { detail: { action: "sendFeedback" } }));
      });
    }, "bn-feedback-overlay");
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(overlay).not.toHaveClass("visible"));
  });
});
