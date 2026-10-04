/**
 * Locale loader — serve mode.
 *
 * Fetches a non-English locale's namespaces on demand. Each locale file is its
 * own lazy chunk, so only the requested one is ever downloaded.
 *
 * The glob below names only the namespaces the SPA requests — `common`,
 * `settings` and `enums`, plus `desktop` on the Mac (`LAZY_NAMESPACES` in
 * ./index). A template-literal import expanded to every namespace on disk,
 * `preflight` and `server` included, and the map of 22 locales × 6 loaders it
 * compiled to was 3.7 kB gzipped of first paint (measured 4 Oct 2026,
 * docs/design-perf-regression-gate.md). **A namespace added to
 * `LAZY_NAMESPACES` must be added to the glob too**, or it resolves as missing
 * in every non-English locale; `localeLoader.test.ts` pins the four.
 *
 * The HTML export cannot use this. It is a single-file build
 * (`inlineDynamicImports: true`), so every chunk the glob produces would be
 * inlined. `vite.export.config.ts` therefore aliases this module to
 * `localeLoader.export.ts`, which has no dynamic import at all, and the export
 * registers the resources the server embeds. See docs/design-export-locale.md.
 *
 * @module i18n/localeLoader
 */

const LOADERS = import.meta.glob<{ default: Record<string, unknown> }>(
  "../../../bristlenose/locales/*/{common,settings,enums,desktop}.json",
);

/** Fetch `namespaces` for `locale`. Missing files resolve via i18next's chain. */
export async function loadLocaleResources(
  locale: string,
  namespaces: readonly string[],
): Promise<Record<string, Record<string, unknown>>> {
  const resources: Record<string, Record<string, unknown>> = {};
  for (const ns of namespaces) {
    const load = LOADERS[`../../../bristlenose/locales/${locale}/${ns}.json`];
    if (!load) continue; // Missing file — the fallback chain covers this namespace.
    try {
      resources[ns] = (await load()).default;
    } catch {
      // Chunk failed to load — the fallback chain covers this namespace.
    }
  }
  return resources;
}
