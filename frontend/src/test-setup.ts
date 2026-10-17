import "@testing-library/jest-dom";
import { afterEach } from "vitest";
import "./i18n";
import { cancelScrollToLand } from "./utils/scrollToLand";

// scrollToLand leaves a settle timer running for 150 ms after a jump. A test
// file that ends inside that window lets it fire after jsdom has torn the
// document down, and "document is not defined" lands as an unhandled error on
// whichever file is running then (CI, 17 Oct 2026, blamed TocSidebar.test.tsx).
afterEach(() => cancelScrollToLand());

// jsdom 27 (under vitest 4) ships NO Web Storage — `localStorage` is
// `undefined`, not empty. Every `localStorage.clear()` in a `beforeEach`
// therefore threw "Cannot read properties of undefined (reading 'clear')"
// and took its whole file down: 170 tests across 10 files, failing for a
// reason that looks nothing like its cause (they read as component bugs).
//
// Storage is load-bearing in this app — appearance, palette, feedback
// drafts, and the pre-serve-mode stores all persist through it — so the
// tests are right to exercise it and the environment is what's missing.
// A spec-shaped in-memory Storage, installed only when absent, so a future
// jsdom that restores the real thing silently wins.
if (typeof globalThis.localStorage === "undefined") {
  const makeStorage = (): Storage => {
    let map = new Map<string, string>();
    return {
      get length() {
        return map.size;
      },
      clear: () => {
        map = new Map();
      },
      getItem: (k: string) => (map.has(k) ? map.get(k)! : null),
      key: (i: number) => Array.from(map.keys())[i] ?? null,
      removeItem: (k: string) => {
        map.delete(k);
      },
      setItem: (k: string, v: string) => {
        map.set(String(k), String(v));
      },
    } as Storage;
  };
  for (const name of ["localStorage", "sessionStorage"] as const) {
    const store = makeStorage();
    Object.defineProperty(globalThis, name, { value: store, configurable: true });
    if (typeof window !== "undefined") {
      Object.defineProperty(window, name, { value: store, configurable: true });
    }
  }
}
