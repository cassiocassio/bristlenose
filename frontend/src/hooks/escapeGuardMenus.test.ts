/**
 * The Escape cascade in useKeyboardShortcuts yields to ANY open `[role="menu"]`
 * (so a menu's Escape does not also clear the search or selection behind it).
 * That is only safe if every menu the app draws closes itself on Escape: a menu
 * that does not would swallow the key and nothing would close.
 *
 * jsdom cannot open each menu cheaply, so this reads the sources, with comments
 * stripped (a word in a comment proves nothing). A menu file must either CALL the
 * shared dropdown hooks (which close on Escape), or be listed in HAND_ROLLED with
 * the minimum number of real Escape handlers it needs. A handler that only
 * `return`s on Escape does not close anything and is not counted. Two files only
 * *mention* the role in a selector and render no menu.
 *
 * Limit: the count is per file, not per menu. The minima below are the handlers
 * that exist today (menu closers plus any unrelated Escape in the same file), so
 * deleting any one of them reddens the test; adding a hand-rolled menu to an
 * unlisted file fails until it is listed here, on purpose.
 */
const sources = import.meta.glob("../**/*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const SELECTOR_ONLY = ["../islands/Dashboard.tsx", "../islands/SessionsTable.tsx"];

/** Hand-rolled menus: file -> minimum real Escape handlers (excluding `Escape) return`). */
const HAND_ROLLED: Record<string, number> = {
  "../components/SearchBox.tsx": 2, // chip menu + search clear
  "../islands/screens/ScreensLens.tsx": 1, // context menu
  "../components/PersonPicker.tsx": 2, // two menus
};

function stripComments(src: string): string {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:"'`])\/\/.*$/gm, "$1");
}

function escapeHandlers(code: string): number {
  return (code.match(/key === "Escape"(?!\)\s*return)/g) ?? []).length;
}

describe("every menu the app draws closes on Escape", () => {
  const menus = Object.entries(sources).filter(
    ([path, src]) =>
      !path.includes(".test.") && src.includes('role="menu"') && !SELECTOR_ONLY.includes(path),
  );

  it("finds the menus (the scan is not empty)", () => {
    expect(menus.length).toBeGreaterThanOrEqual(7);
  });

  it("every hand-rolled entry still renders a menu", () => {
    const paths = menus.map(([path]) => path);
    for (const file of Object.keys(HAND_ROLLED)) expect(paths).toContain(file);
  });

  it.each(menus.map(([path]) => path))("%s closes on Escape", (path) => {
    const code = stripComments(sources[path]);
    if (path in HAND_ROLLED) {
      expect(escapeHandlers(code)).toBeGreaterThanOrEqual(HAND_ROLLED[path]);
    } else {
      expect(code).toMatch(/\buse(Dropdown|MenuKeyboard)\(/);
    }
  });
});
