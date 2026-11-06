/**
 * The Escape cascade in useKeyboardShortcuts yields to ANY open `[role="menu"]`
 * (so a menu's Escape does not also clear the search or selection behind it).
 * That is only safe if every menu the app draws closes itself on Escape: a menu
 * that does not would swallow the key and nothing would close.
 *
 * jsdom cannot open each menu cheaply, so this reads the sources: every
 * component that renders `role="menu"` must either use the shared dropdown
 * hooks (which close on Escape) or handle Escape itself. Two files only
 * *mention* the role in a selector and render no menu.
 */
const sources = import.meta.glob("../**/*.tsx", {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const SELECTOR_ONLY = ["../islands/Dashboard.tsx", "../islands/SessionsTable.tsx"];

describe("every menu the app draws closes on Escape", () => {
  const menus = Object.entries(sources).filter(
    ([path, src]) => !path.includes(".test.") && src.includes('role="menu"') && !SELECTOR_ONLY.includes(path),
  );

  it("finds the menus (the scan is not empty)", () => {
    expect(menus.length).toBeGreaterThanOrEqual(7);
  });

  it.each(menus.map(([path]) => path))("%s closes on Escape", (path) => {
    const src = sources[path];
    const usesSharedHooks = /useDropdown|useMenuKeyboard/.test(src);
    const handlesEscape = src.includes("Escape");
    expect(usesSharedHooks || handlesEscape).toBe(true);
  });
});
