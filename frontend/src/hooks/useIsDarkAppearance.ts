/**
 * useIsDarkAppearance — is the report painting dark right now?
 *
 * Two surfaces carry that fact two different ways, and only reading one of
 * them pins the other to light for ever:
 *
 * - **Browser serve mode.** The web appearance picker *forces* a choice by
 *   writing `data-theme="light|dark"` on `<html>` (`applyTheme` in
 *   SettingsModal / SettingsPanel, plus the pre-paint boot script in
 *   `index.html`). An explicit override outranks the OS — that's what picking
 *   it means. "Auto" removes the attribute rather than setting it.
 * - **Desktop embedded mode.** `data-theme` is never written at all.
 *   Appearance is owned natively via `NSApp.appearance`, the WKWebView
 *   inherits it, and the report CSS follows `prefers-color-scheme`. There is
 *   deliberately no bridge channel for it (see the comment in
 *   `BridgeHandler.swift` — a second channel for a fact the platform already
 *   carries was removed on purpose), and embedded mode intercepts the web
 *   Settings modal in favour of native Settings, so `applyTheme` never runs.
 *
 * Hence: honour an explicit `data-theme` when present, else fall back to the
 * media query. Subscribe to **both** signals, because either can change under
 * a live report — the native side no longer remounts the webview on an
 * appearance switch, so nothing else would repaint us.
 *
 * @module useIsDarkAppearance
 */

import { useEffect, useState } from "react";

const DARK_QUERY = "(prefers-color-scheme: dark)";

function readIsDark(): boolean {
  const forced = document.documentElement.getAttribute("data-theme");
  if (forced === "dark") return true;
  if (forced === "light") return false;
  // No override — follow the host. jsdom ships no `matchMedia`, so guard
  // rather than assume; treating its absence as light matches the CSS default.
  return typeof window.matchMedia === "function"
    ? window.matchMedia(DARK_QUERY).matches
    : false;
}

export function useIsDarkAppearance(): boolean {
  const [isDark, setIsDark] = useState(readIsDark);

  useEffect(() => {
    const sync = () => setIsDark(readIsDark());

    const observer = new MutationObserver(sync);
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ["data-theme"],
    });

    const mq =
      typeof window.matchMedia === "function" ? window.matchMedia(DARK_QUERY) : null;
    mq?.addEventListener("change", sync);

    // Either signal may have moved between first render and this effect.
    sync();

    return () => {
      observer.disconnect();
      mq?.removeEventListener("change", sync);
    };
  }, []);

  return isDark;
}
