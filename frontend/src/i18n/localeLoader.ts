/**
 * Locale loader — serve mode.
 *
 * Fetches a non-English locale's namespaces on demand.  Vite compiles the
 * template-literal import below into a glob over `locales/<lang>/<ns>.json`,
 * which is correct here: code-splitting means each locale becomes its own lazy
 * chunk and only the requested one is ever downloaded.
 *
 * Placeholders, not the literal glob: spelling it out puts the block-comment
 * terminator inside this comment. The zero-width space that used to hide it
 * was invisible in every editor and failed `no-irregular-whitespace` in CI.
 *
 * The HTML export cannot use this. It is a single-file build
 * (`inlineDynamicImports: true`), so every chunk the glob produces is inlined —
 * all 192 files, 1,802 KB, roughly half the exported report, including
 * namespaces a browser cannot reach. `vite.export.config.ts` therefore aliases
 * this module to `localeLoader.export.ts`, which has no dynamic import at all.
 * A build-time flag would NOT be enough: vite's dynamic-import-vars plugin
 * expands the glob during transform, before any dead-code elimination could
 * remove the branch. See docs/design-export-locale.md.
 *
 * @module i18n/localeLoader
 */

/** Fetch `namespaces` for `locale`. Missing files resolve via i18next's chain. */
export async function loadLocaleResources(
  locale: string,
  namespaces: readonly string[],
): Promise<Record<string, Record<string, unknown>>> {
  const resources: Record<string, Record<string, unknown>> = {};
  for (const ns of namespaces) {
    try {
      const mod = await import(`../../../bristlenose/locales/${locale}/${ns}.json`);
      resources[ns] = mod.default ?? mod;
    } catch {
      // Missing file — the fallback chain covers this namespace.
    }
  }
  return resources;
}
