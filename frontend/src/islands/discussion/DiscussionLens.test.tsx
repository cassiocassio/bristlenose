import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import fixture from "./fixture.json";
import { DiscussionLens, DiscussionView } from "./DiscussionLens";
import { joinNames } from "./loadDiscussion";
import i18n from "../../i18n";
import enDesktop from "@locales/en/desktop.json";
import { _resetPlatformCache } from "../../utils/platform";
import { _resetEmbeddedCache } from "../../utils/embedded";
import { resetLensState } from "./lensState";
import type { DiscussionData } from "./types";

const data = fixture as unknown as DiscussionData;

function nav() {
  return screen.getByRole("navigation", { name: "Discussion guide" });
}

function heading() {
  return screen.getByRole("heading", { level: 1 }).textContent;
}

beforeEach(() => {
  resetLensState();
  document.getElementById("bn-app-root")?.remove();
});

describe("DiscussionView", () => {
  it("opens on Merged and the first session, with the session's questions and quotes", () => {
    const { container } = render(<DiscussionView data={data} />);
    expect(screen.getByRole("radio", { name: "Normalised questions" })).toHaveAttribute("aria-checked", "true");
    expect(heading()).toBe("Session 1");
    const asked = data.turns.filter((t) => t.session === "s1" && t.item).length;
    expect(container.querySelectorAll(".dl-content .dl-ask")).toHaveLength(asked);
    const quotes = data.quotes.filter((q) => q.session === "s1").length;
    expect(container.querySelectorAll(".dl-content blockquote.quote-card:not(.dl-ask)")).toHaveLength(quotes);
  });

  it("Merged shows the promoted new section, without a badge (as mocked up)", () => {
    render(<DiscussionView data={data} />);
    const emergent = data.sections.find((s) => s.origin === "emergent")!;
    const head = within(nav()).getByText(emergent.title, { exact: false });
    expect(head.closest(".toc-heading")!.querySelector(".badge")).toBeNull();
  });

  it("Planned shows the guide as written, every line with the solid dot", () => {
    const { container } = render(<DiscussionView data={data} />);
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    const rows = container.querySelectorAll(".dl-nav .dl-row");
    expect(rows).toHaveLength(data.spine.reduce((n, s) => n + s.items.length, 0));
    expect(container.querySelectorAll(".dl-nav .dl-dot.hollow")).toHaveLength(0);
    expect(container.querySelectorAll(".dl-nav .dl-mk .dl-dot")).toHaveLength(rows.length);
  });

  it("a header session switches the column and marks itself as here", () => {
    render(<DiscussionView data={data} />);
    const s2 = data.sessions[1];
    const btn = screen.getByRole("radio", { name: new RegExp(`^#${s2.number}`) });
    fireEvent.click(btn);
    expect(heading()).toBe(`Session ${s2.number}`);
    expect(btn).toHaveAttribute("aria-checked", "true");
    // option C: the navigator's selection vocabulary, no ring
    expect(btn.querySelector(".dl-here .bn-person-badge")).not.toBeNull();
    expect(btn.querySelector(".bn-person-badge-highlighted")).toBeNull();
  });

  it("digit keys pick a session, unless another handler already claimed the key", () => {
    render(<DiscussionView data={data} />);
    fireEvent.keyDown(document, { key: "3" });
    expect(heading()).toBe("Session 3");
    const ev = new KeyboardEvent("keydown", { key: "1", bubbles: true, cancelable: true });
    ev.preventDefault();
    act(() => {
      document.dispatchEvent(ev);
    });
    expect(heading()).toBe("Session 3");
  });

  it("clicking a row locks focus on its questions; clicking again or Esc clears it", () => {
    const { container } = render(<DiscussionView data={data} />);
    const it = data.sections.flatMap((s) => s.items).find((i) => i.asks.some((a) => a.session === "s1"))!;
    const row = container.querySelector(`.dl-row[data-id="${it.id}"] .dl-row-btn`)!;
    fireEvent.click(row);
    expect(container.querySelector(".dl-lens")).toHaveClass("has-focus");
    const hot = [...container.querySelectorAll(".dl-ask.hot")].map((e) => (e as HTMLElement).dataset.item);
    expect(hot.length).toBeGreaterThan(0);
    expect(new Set(hot)).toEqual(new Set([it.id]));
    fireEvent.click(row);
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
    fireEvent.click(row);
    fireEvent.keyDown(document, { key: "Escape" });
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
  });

  it("focusing a row the current session never asked jumps to a session that did", () => {
    const { container } = render(<DiscussionView data={data} />);
    const elsewhere = data.sections.flatMap((s) => s.items)
      .find((i) => i.asks.length && !i.asks.some((a) => a.session === "s1"))!;
    const first = data.sessions.find((s) => elsewhere.asks.some((a) => a.session === s.id))!;
    fireEvent.click(container.querySelector(`.dl-row[data-id="${elsewhere.id}"] .dl-row-btn`)!);
    expect(heading()).toBe(`Session ${first.number}`);
    expect(container.querySelector(".dl-ask.hot")).not.toBeNull();
  });

  it("clicking a question focuses that one ask, and its quotes, only", () => {
    const { container } = render(<DiscussionView data={data} />);
    const answered = container.querySelector(".dl-group .dl-ask + blockquote.quote-card:not(.dl-ask)")!
      .previousElementSibling as HTMLElement;
    fireEvent.click(within(answered).getByRole("button", { pressed: false }));
    expect(container.querySelectorAll(".dl-ask.hot")).toHaveLength(1);
    const lit = container.querySelectorAll(`blockquote.quote-card.hot[data-for="${answered.dataset.turn}"]`);
    expect(lit.length).toBeGreaterThan(0);
  });

  it("a session badge in a row selects that session and focuses the row", () => {
    const { container } = render(<DiscussionView data={data} />);
    const multi = data.sections.flatMap((s) => s.items).find((i) => new Set(i.asks.map((a) => a.session)).size > 1)!;
    const target = data.sessions.find((s) => s.id !== "s1" && multi.asks.some((a) => a.session === s.id))!;
    const chip = container.querySelector(`.dl-row[data-id="${multi.id}"] .dl-chips`)!;
    fireEvent.click(within(chip as HTMLElement).getByRole("button", { name: new RegExp(`^#${target.number} `) }));
    expect(heading()).toBe(`Session ${target.number}`);
    expect(container.querySelector(`.dl-row[data-id="${multi.id}"]`)).toHaveClass("active");
  });

  it("the split is a keyboard-operable separator that remembers its width", () => {
    render(<DiscussionView data={data} />);
    const split = screen.getByRole("separator", { name: "Resize the discussion guide" });
    fireEvent.keyDown(split, { key: "Home" });
    expect(split).toHaveAttribute("aria-valuenow", "200");
    fireEvent.keyDown(split, { key: "ArrowRight" });
    // jsdom measures every width as 0, so the step lands relative to the floor
    expect(Number(split.getAttribute("aria-valuenow"))).toBeGreaterThanOrEqual(200);
  });

  it("names a group session in the list form, capped past two", () => {
    const group: DiscussionData = {
      ...data,
      sessions: data.sessions.map((s, i) => i === 0 ? { ...s, participants: [
        { code: "p1", name: "Bettina" }, { code: "p5", name: "Priya" }, { code: "p6", name: "Christopher" },
      ] } : s),
    };
    render(<DiscussionView data={group} />);
    expect(screen.getByRole("radio", { name: /^#1/ }).textContent).toContain("Bettina and 2 others");
    expect(screen.getByRole("radio", { name: /^#1/ })).toHaveAttribute("title", "Session 1: Bettina, Priya and Christopher");
    // the accessible name carries the visible "#1" and every name in full
    expect(screen.getByRole("radio", { name: "#1 Bettina, Priya and Christopher" })).toBeInTheDocument();
  });
});

describe("review fixes, 3 Oct 2026", () => {
  it("arrow keys move the session radio group, with one tab stop", () => {
    render(<DiscussionView data={data} />);
    const radios = within(screen.getByRole("radiogroup", { name: "Sessions" })).getAllByRole("radio");
    expect(radios.map((r) => r.tabIndex)).toEqual([0, -1, -1]);
    fireEvent.keyDown(radios[0], { key: "ArrowRight" });
    expect(heading()).toBe("Session 2");
    fireEvent.keyDown(radios[1], { key: "End" });
    expect(heading()).toBe("Session 3");
    fireEvent.keyDown(radios[2], { key: "ArrowRight" });  // wraps
    expect(heading()).toBe("Session 1");
  });

  it("digit keys do nothing while a dialog owns the keyboard", () => {
    const root = document.createElement("div");
    root.id = "bn-app-root";
    document.body.appendChild(root);
    render(<DiscussionView data={data} />);
    root.setAttribute("inert", "");
    fireEvent.keyDown(document, { key: "2" });
    expect(heading()).toBe("Session 1");
    root.removeAttribute("inert");
    fireEvent.keyDown(document, { key: "2" });
    expect(heading()).toBe("Session 2");
  });

  it("clearing a row's focus never moves the reader to another session", () => {
    const { container } = render(<DiscussionView data={data} />);
    const elsewhere = data.sections.flatMap((s) => s.items)
      .find((i) => i.asks.length && !i.asks.some((a) => a.session === "s1"))!;
    const btn = container.querySelector(`.dl-row[data-id="${elsewhere.id}"] .dl-row-btn`)!;
    fireEvent.click(btn);                         // jumps to a session that asked it
    const landed = heading();
    fireEvent.keyDown(document, { key: "1" });    // reader moves on
    fireEvent.click(btn);                         // still focused on the row: this clears
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
    expect(heading()).toBe("Session 1");
    expect(landed).not.toBe("Session 1");
  });

  it("names the views Normalised questions then Your guide, in that order", () => {
    render(<DiscussionView data={data} />);
    const radios = within(screen.getByRole("radiogroup", { name: "Show" })).getAllByRole("radio");
    expect(radios.map((r) => r.textContent)).toEqual(["Normalised questions", "Your guide"]);
    expect(radios.map((r) => r.getAttribute("title"))).toEqual([
      "What was asked in every session, merged with your guide",
      "Your discussion guide, as written",
    ]);
  });

  it("Your guide offers Summary or Original; Original shows the guide's own wording", () => {
    const { container } = render(<DiscussionView data={data} />);
    expect(screen.queryByRole("radiogroup", { name: "Show your guide as" })).toBeNull();
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    const views = screen.getByRole("radiogroup", { name: "Show your guide as" });
    expect(within(views).getByRole("radio", { name: "Summary" })).toBeChecked();
    const first = data.spine.find((sec) => sec.items.length && sec.kind !== "instruction")!.items[0];
    const text = () => container.querySelector(`.dl-row[data-id="${first.id}"] .dl-tx`)!.textContent;
    expect(text()).toBe(first.terse);
    fireEvent.click(within(views).getByRole("radio", { name: "Original" }));
    expect(text()).toBe(first.text);
  });

  it("a line never asked in any session does not take focus (no dead click)", () => {
    const { container } = render(<DiscussionView data={data} />);
    const never = data.sections.flatMap((s) => s.items).find((i) => !i.asks.length)!;
    const btn = container.querySelector(`.dl-row[data-id="${never.id}"] .dl-row-btn`)!;
    expect(btn).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(btn);
    expect(container.querySelector(".dl-lens")).not.toHaveClass("has-focus");
    expect(heading()).toBe("Session 1");
  });

  it("with no guide there is no Planned view to offer", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    expect(screen.queryByRole("radio", { name: "Your guide" })).toBeNull();
  });

  it("a turn the model never classified is shown, marked, and wired to nothing", () => {
    const t = data.turns.find((x) => x.session === "s1" && x.kind === "chat")!;
    const d = { ...data, turns: data.turns.map((x) => (x.id === t.id ? { ...x, kind: "unclassified" as const } : x)) };
    const { container } = render(<DiscussionView data={d} />);
    const row = container.querySelector(`.dl-ask[data-turn="${t.id}"]`)!;
    expect(row).not.toBeNull();
    expect(row.textContent).toContain("not classified");
    expect((row as HTMLElement).dataset.item).toBe("");
  });

  it("offers to add or replace the guide with the house small button, and says where the guide goes", () => {
    const { unmount } = render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    const add = screen.getByRole("button", { name: "Add your guide…" });
    expect(add).toHaveClass("bn-btn", "bn-btn-secondary", "bn-btn-sm");
    fireEvent.click(add);
    expect(screen.getByRole("status").textContent).toMatch(/folder named “Discussion guide”/);
    unmount();
    render(<DiscussionView data={data} />);
    expect(screen.queryByRole("button", { name: /your guide…/ })).toBeNull(); // Normalised, with a guide
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    expect(screen.getByRole("button", { name: "Replace your guide…" })).toBeInTheDocument();
  });

  it("Normalised questions carries a small key of the marks; Your guide does not", () => {
    render(<DiscussionView data={data} />);
    const key = screen.getByRole("note", { name: "Key" });
    expect(key).toHaveClass("bn-pipeline-key");
    for (const t of ["Asked as planned", "Planned, never asked", "Not in your guide", "Grey: not asked in this session"]) {
      expect(within(key).getByText(t, { exact: false })).toBeInTheDocument();
    }
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    expect(screen.queryByRole("note", { name: "Key" })).toBeNull();
  });

  it("each mark explains itself on hover, the house ? cursor way", () => {
    const { container } = render(<DiscussionView data={data} />);
    const tips = new Set([...container.querySelectorAll(".dl-row .dl-mk")].map((m) => m.getAttribute("title")));
    expect(tips).toEqual(new Set([
      "In your guide, and asked", "In your guide, never asked in any session",
      "Not in your guide — asked as it came up",
    ]));
  });

  it("every navigator row says its provenance in words, not only by its mark", () => {
    const { container } = render(<DiscussionView data={data} />);
    const rows = [...container.querySelectorAll(".dl-row-btn")];
    expect(rows.length).toBeGreaterThan(0);
    for (const r of rows) expect(r.querySelector(".bn-sr-only")!.textContent).toMatch(/planned|not in the guide/);
  });

  it("section titles in the navigator are headings, labelling their rows", () => {
    render(<DiscussionView data={data} />);
    const first = data.sections.find((s) => s.items.length)!;
    expect(within(nav()).getByRole("group", { name: new RegExp(first.title) })).toBeInTheDocument();
    expect(within(nav()).getAllByRole("heading", { level: 2 }).length).toBe(data.sections.length);
  });

  it("collapsed badge rows stay collapsed frame after frame (no measure-of-hidden flicker)", async () => {
    // jsdom measures nothing: give the badges a width only while they are shown,
    // which is exactly the browser behaviour that made a collapsed row reopen.
    const desc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollWidth");
    const navDesc = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    Object.defineProperty(HTMLElement.prototype, "scrollWidth", {
      configurable: true,
      get(this: HTMLElement) {
        if (!this.classList.contains("dl-chips")) return 0;
        return this.closest(".dl-row")?.classList.contains("compact") ? 0 : 50 * this.children.length;
      },
    });
    Object.defineProperty(HTMLElement.prototype, "clientWidth", {
      configurable: true,
      get(this: HTMLElement) {
        return this.classList.contains("dl-nav") ? 300 : 0;
      },
    });
    try {
      const { container } = render(<DiscussionView data={data} />);
      const frames = async () => act(async () => {
        await new Promise((r) => setTimeout(r, 40));
      });
      await frames();
      const after1 = [...container.querySelectorAll(".dl-row.compact")].map((r) => (r as HTMLElement).dataset.id);
      expect(after1.length).toBeGreaterThan(0); // 3 badges × 50 > 30% of 300
      // every frame, not two frames apart: a flicker alternates, so comparing
      // frames an even distance apart would pass it (it did, on the first draft)
      for (let i = 0; i < 3; i++) {
        fireEvent.scroll(window);
        await frames();
        const now = [...container.querySelectorAll(".dl-row.compact")].map((r) => (r as HTMLElement).dataset.id);
        expect(now).toEqual(after1);
      }
    } finally {
      if (desc) Object.defineProperty(HTMLElement.prototype, "scrollWidth", desc);
      if (navDesc) Object.defineProperty(HTMLElement.prototype, "clientWidth", navDesc);
    }
  });

  it("remembers mode, session and focus across a lens switch", () => {
    const first = render(<DiscussionView data={data} />);
    fireEvent.click(screen.getByRole("radio", { name: "Your guide" }));
    fireEvent.keyDown(document, { key: "3" });
    first.unmount();
    render(<DiscussionView data={data} />);
    expect(screen.getByRole("radio", { name: "Your guide" })).toHaveAttribute("aria-checked", "true");
    expect(heading()).toBe("Session 3");
  });
});

// The record as the server sends it: codes only. Built from the synthetic
// fixture so the shape matches the lens's own data.
const record = {
  ...data,
  sessions: data.sessions.map((s) => ({ ...s, participants: s.participants.map((p) => p.code) })),
  quotes: data.quotes.map(({ key: _key, name: _name, ...q }) => q),
};
const sessionList = data.sessions.map((s) => ({
  session_id: s.id,
  session_number: s.number,
  session_date: null,
  speakers: s.participants.map((p) => ({ speaker_code: p.code, name: p.name, role: "participant" })),
}));

const api = vi.hoisted(() => ({ apiGet: vi.fn(), getSessionList: vi.fn() }));
vi.mock("../../utils/api", () => api);
const bridge = vi.hoisted(() => ({ postProjectAction: vi.fn() }));
vi.mock("../../shims/bridge", async (orig) => ({
  ...(await orig<typeof import("../../shims/bridge")>()),
  postProjectAction: bridge.postProjectAction,
}));
const exportState = vi.hoisted(() => ({ on: false }));
vi.mock("../../utils/exportData", async (orig) => ({
  ...(await orig<typeof import("../../utils/exportData")>()),
  isExportMode: () => exportState.on,
}));

function serve(status: string, rec: unknown) {
  api.apiGet.mockResolvedValue({ status, record: rec });
  api.getSessionList.mockResolvedValue(sessionList);
}

describe("DiscussionLens", () => {
  it("loads the record, joins names from the sessions, and renders the lens", async () => {
    serve("ready", record);
    render(<DiscussionLens />);
    expect(await screen.findByTestId("discussion-lens")).toBeInTheDocument();
    expect(api.apiGet).toHaveBeenCalledWith("/discussion");
  });

  it.each([
    ["not_run", null, /no discussion for this project yet/],
    ["stale", null, /quotes have changed since the discussion was built/],
    ["failed", record, /could not be built for this project/],
  ])("says what a %s record means and what to do", async (status, rec, text) => {
    serve(status, rec);
    render(<DiscussionLens />);
    expect(await screen.findByText(text)).toBeInTheDocument();
    expect(screen.queryByTestId("discussion-lens")).toBeNull();
  });

  it.each([
    ["no_moderator", /Discussion lens is for moderated interviews/],
    ["moderator_unreliable", /could not be told apart reliably in any session/],
    ["failed", /could not be built for this project/],
  ])("a failed record whose sessions are all %s says why — re-analyse only where it helps", async (state, text) => {
    serve("failed", { ...record, sessions: record.sessions.map((s) => ({ ...s, state })) });
    render(<DiscussionLens />);
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it("a server failure is said, not shown as an empty lens", async () => {
    api.apiGet.mockRejectedValue(new Error("GET /discussion 500"));
    api.getSessionList.mockResolvedValue(sessionList);
    render(<DiscussionLens />);
    expect(await screen.findByRole("alert")).toHaveTextContent("could not be loaded");
  });
});

describe("platform and export copy", () => {
  afterEach(() => {
    exportState.on = false;
    delete document.documentElement.dataset.platform;
    _resetPlatformCache();
  });

  it("the CLI is told to run bristlenose run again", async () => {
    serve("not_run", null);
    render(<DiscussionLens />);
    expect(await screen.findByText(/Run bristlenose run on the project folder again/)).toBeInTheDocument();
  });

  it("the Mac is never sent to Re-analyse, which starts over and discards edits", async () => {
    document.documentElement.dataset.platform = "desktop";
    _resetPlatformCache();
    // The app registers the desktop namespace at start-up when <html> says
    // desktop; this test flips the platform after start-up, so register it here.
    i18n.addResourceBundle("en", "desktop", enDesktop, true, true);
    for (const [status, says] of [
      ["not_run", /choose Analyse from the project’s menu in the sidebar/],
      ["stale", /next time the project is analysed/],
    ] as const) {
      serve(status, null);
      const { unmount } = render(<DiscussionLens />);
      const text = (await screen.findByText(says)).textContent ?? "";
      expect(text).not.toMatch(/re-analyse|bristlenose run/i);
      unmount();
    }
  });

  it("an exported report's reader gets one plain line, not an instruction", async () => {
    exportState.on = true;
    serve("not_run", null);
    render(<DiscussionLens />);
    expect(await screen.findByText("No discussion was built for this report.")).toBeInTheDocument();
  });
});

describe("the guide button in the Mac app", () => {
  afterEach(() => {
    delete (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__;
    _resetEmbeddedCache();
    bridge.postProjectAction.mockReset();
  });

  it("asks the app for its native panel instead of describing the folder", () => {
    (window as unknown as Record<string, unknown>).__BRISTLENOSE_EMBEDDED__ = true;
    _resetEmbeddedCache();
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add your guide…" }));
    expect(bridge.postProjectAction).toHaveBeenCalledWith("choose-discussion-guide");
    expect(screen.queryByText(/folder named “Discussion guide”/)).toBeNull();
  });

  it("in a browser it says where the guide goes, and asks nothing of a host", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [] }} />);
    fireEvent.click(screen.getByRole("button", { name: "Add your guide…" }));
    expect(bridge.postProjectAction).not.toHaveBeenCalled();
    expect(screen.getByText(/folder named “Discussion guide”/)).toBeInTheDocument();
  });
});

describe("joinNames", () => {
  it("names a code from its own session: p1 is a different person in each", () => {
    const two = {
      ...record,
      sessions: [
        { ...record.sessions[0], id: "s1", participants: ["p1"] },
        { ...record.sessions[0], id: "s2", participants: ["p1"] },
      ],
      quotes: [],
    };
    const list = [
      { session_id: "s1", session_number: 1, session_date: null, speakers: [{ speaker_code: "p1", name: "Asha", role: "participant" }] },
      { session_id: "s2", session_number: 2, session_date: null, speakers: [{ speaker_code: "p1", name: "Ben", role: "participant" }] },
    ];
    const joined = joinNames(two as never, list);
    expect(joined.sessions.map((s) => s.participants[0].name)).toEqual(["Asha", "Ben"]);
  });

  it("names each participant and quote from its own session, by code", () => {
    const joined = joinNames(record as never, sessionList);
    expect(joined.sessions[0].participants).toEqual(data.sessions[0].participants);
    expect(joined.quotes[0].name).toBe(data.quotes[0].name);
  });

  it("leaves a name the sessions list blanked (an anonymised export) blank", () => {
    const blank = sessionList.map((s) => ({ ...s, speakers: s.speakers.map((sp) => ({ ...sp, name: "" })) }));
    const joined = joinNames(record as never, blank);
    expect(joined.sessions.every((s) => s.participants.every((p) => p.name === ""))).toBe(true);
    expect(joined.quotes.every((q) => q.name === "")).toBe(true);
  });
});

describe("language", () => {
  afterEach(async () => {
    await act(async () => { await i18n.changeLanguage("en"); });
  });

  it("re-renders in the new language without remounting (the getters are read live)", async () => {
    render(<DiscussionView data={data} />);
    expect(heading()).toBe("Session 1");
    i18n.addResourceBundle("xx", "common", { discussion: { session: "Sitzung {{n}}" } }, true, true);
    await act(async () => { await i18n.changeLanguage("xx"); });
    expect(heading()).toBe("Sitzung 1");
  });
});

describe("degraded records", () => {
  it("a guide that is there but unread says why", () => {
    render(<DiscussionView data={{ ...data, guide: false, spine: [], guide_problem: "unsupported_format" }} />);
    expect(screen.getByText(/format Bristlenose can’t read/)).toBeInTheDocument();
  });

  it("a session that could not be read says so, never 'no questions'", () => {
    const sessions = data.sessions.map((s, i) => (i === 0 ? { ...s, state: "failed" as const } : s));
    render(<DiscussionView data={{ ...data, sessions }} />);
    expect(screen.getByText(/questions could not be classified/)).toBeInTheDocument();
    expect(screen.queryByText("No questions found in this session")).toBeNull();
  });
});
