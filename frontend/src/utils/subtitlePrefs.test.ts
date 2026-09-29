import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  _resetSubtitlePrefsForTests,
  getSubtitlePrefs,
  setSubtitlePref,
  subscribeSubtitlePrefs,
  toggleSubtitlePref,
} from "./subtitlePrefs";

beforeEach(() => {
  localStorage.clear();
  _resetSubtitlePrefsForTests();
});

describe("subtitlePrefs", () => {
  it("defaults both preferences to off", () => {
    expect(getSubtitlePrefs()).toEqual({ playerSubtitles: false, burnSubtitles: false });
  });

  it("persists a toggle and notifies subscribers", () => {
    const fn = vi.fn();
    const off = subscribeSubtitlePrefs(fn);
    toggleSubtitlePref("burnSubtitles");
    expect(getSubtitlePrefs().burnSubtitles).toBe(true);
    expect(localStorage.getItem("bristlenose-burn-subtitles")).toBe("true");
    expect(fn).toHaveBeenCalledOnce();
    off();
  });

  it("does not notify when the value is unchanged", () => {
    const fn = vi.fn();
    const off = subscribeSubtitlePrefs(fn);
    setSubtitlePref("playerSubtitles", false);
    expect(fn).not.toHaveBeenCalled();
    off();
  });

  it("follows a change made in another tab", () => {
    const fn = vi.fn();
    const off = subscribeSubtitlePrefs(fn);
    localStorage.setItem("bristlenose-player-subtitles", "true");
    window.dispatchEvent(new StorageEvent("storage", { key: "bristlenose-player-subtitles" }));
    expect(getSubtitlePrefs().playerSubtitles).toBe(true);
    expect(fn).toHaveBeenCalledOnce();
    off();
  });

  it("reads a stored preference on reload", () => {
    localStorage.setItem("bristlenose-player-subtitles", "true");
    _resetSubtitlePrefsForTests();
    expect(getSubtitlePrefs().playerSubtitles).toBe(true);
  });
});
