/**
 * The person picker on a surface that does not hold /sessions itself — the
 * transcript and the dashboard (docs/design-people.md §J8.7). The trigger
 * reads the speaker fresh when it opens, and its writes are the grid's: a
 * pick names the person, someone new carries a client-made uuid, and the page
 * is told to re-read once the write has landed.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import { SpeakerPickerTrigger } from "./SpeakerPickerTrigger";
import { resetUndoStore } from "../contexts/UndoStore";
import { _resetExportCache } from "../utils/exportData";
import { resetSpeakerNameQueue } from "../utils/speakerNames";
import { SPEAKERS_WRITTEN_EVENT, resetNativePicker } from "../utils/speakerPicking";

const sessions = {
  sessions: [
    {
      session_id: "s1",
      speakers: [
        { speaker_code: "m1", slot_code: "m1", name: "Sarah", role: "researcher", name_confirmed: true, person: "id-sarah" },
        { speaker_code: "p1", slot_code: "p1", name: "", role: "participant", name_confirmed: false },
      ],
    },
    {
      session_id: "s2",
      speakers: [
        { speaker_code: "m2", slot_code: "m1", name: "Kerri", role: "researcher", name_confirmed: true, person: "id-kerri" },
      ],
    },
  ],
};

function puts(): { url: string; body: unknown }[] {
  return (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls
    .filter(([, init]) => (init as RequestInit | undefined)?.method === "PUT")
    .map(([url, init]) => ({ url: url as string, body: JSON.parse((init as RequestInit).body as string) }));
}

const pickerMenu = () =>
  waitFor(() => {
    const el = document.querySelector<HTMLElement>(".bn-person-picker");
    if (!el) throw new Error("picker not open yet");
    return el;
  });

beforeEach(() => {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) =>
      Promise.resolve({
        ok: true,
        json: async () => (url.includes("/sessions") && !url.includes("/speakers/") ? sessions : { status: "ok" }),
      }),
    ),
  );
});

afterEach(() => {
  resetUndoStore();
  resetSpeakerNameQueue();
  resetNativePicker();
  vi.unstubAllGlobals();
});

describe("SpeakerPickerTrigger", () => {
  it("opens the picker on the speaker, read fresh, with every moderator in the study", async () => {
    render(<SpeakerPickerTrigger sessionId="s1" code="m1" role="moderator" name="Sarah" />);
    fireEvent.click(screen.getByTestId("bn-speaker-trigger-m1"));
    const picker = await pickerMenu();
    const rows = Array.from(picker.querySelectorAll(".bn-speaker-badge-name")).map((n) => n.textContent);
    expect(rows.slice(0, 2)).toEqual(["Sarah", "Kerri"]);
  });

  it("a pick writes the person to the slot, by its slot code, and the page is told", async () => {
    const written = vi.fn();
    window.addEventListener(SPEAKERS_WRITTEN_EVENT, written);
    try {
      render(<SpeakerPickerTrigger sessionId="s1" code="m1" role="moderator" name="Sarah" />);
      fireEvent.click(screen.getByTestId("bn-speaker-trigger-m1"));
      const kerri = Array.from((await pickerMenu()).querySelectorAll<HTMLElement>(".export-dropdown-item"))[1];
      fireEvent.click(kerri);
      await waitFor(() => expect(puts()).toHaveLength(1));
      expect(puts()[0].url).toMatch(/\/sessions\/s1\/speakers\/m1$/);
      expect(puts()[0].body).toEqual({ person: "id-kerri", short_name: "Kerri", confirmed: true, kind: "moderator" });
      await waitFor(() => expect(written).toHaveBeenCalled());
    } finally {
      window.removeEventListener(SPEAKERS_WRITTEN_EVENT, written);
    }
  });

  it("someone new is typed where an unknown participant opens, and named for that code", async () => {
    render(<SpeakerPickerTrigger sessionId="s1" code="p1" role="participant" />);
    fireEvent.click(screen.getByTestId("bn-speaker-trigger-p1"));
    await pickerMenu();
    const field = screen.getByPlaceholderText("New name for p1");
    expect(document.activeElement).toBe(field);
    fireEvent.change(field, { target: { value: "Wylie E. Coyote" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await waitFor(() => expect(puts().length).toBeGreaterThan(0));
    expect(puts()[0].url).toMatch(/\/people$/);
  });

  it("a name another moderator goes by is refused, and nothing is written (§J8.11)", async () => {
    render(<SpeakerPickerTrigger sessionId="s1" code="m1" role="moderator" name="Sarah" />);
    fireEvent.click(screen.getByTestId("bn-speaker-trigger-m1"));
    await pickerMenu();
    const field = screen.getByPlaceholderText("New moderator");
    fireEvent.change(field, { target: { value: "kerri" } });
    fireEvent.keyDown(field, { key: "Enter" });
    await new Promise((r) => setTimeout(r, 20));
    expect(puts()).toHaveLength(0);
  });

  it("a paragraph's badge is a click target, not a Tab stop", () => {
    render(<SpeakerPickerTrigger sessionId="s1" code="m1" role="moderator" tabbable={false} />);
    expect(screen.getByTestId("bn-speaker-trigger-m1").getAttribute("tabindex")).toBe("-1");
  });

  it("an exported report draws the badge plain, with no picker", () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = {
      version: 1, exported_at: "2026-10-06T00:00:00Z", health: {}, endpoints: {},
    };
    _resetExportCache();
    try {
      render(<SpeakerPickerTrigger sessionId="s1" code="m1" role="moderator" name="Sarah" />);
      expect(screen.queryByTestId("bn-speaker-trigger-m1")).toBeNull();
      expect(screen.getByText("Sarah")).toBeInTheDocument();
    } finally {
      delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
      _resetExportCache();
    }
  });
});
