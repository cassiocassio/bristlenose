/**
 * Locale loader — HTML export build.
 *
 * Aliased over `localeLoader.ts` by `vite.export.config.ts`. It exists to be
 * *empty*: an exported report carries its locale resources in
 * `BRISTLENOSE_EXPORT.localeResources`, embedded by the server for the chosen
 * language and everything it falls back to, so there is nothing to fetch — and
 * an offline `file://` artefact has nowhere to fetch it from anyway.
 *
 * Keeping the sibling's dynamic import out of this build is the entire point.
 * With `inlineDynamicImports: true` its glob would inline all 22 locales × 9
 * namespaces, which is what this change removes.
 *
 * @module i18n/localeLoader.export
 */

/** Always empty: the export's resources are registered from the embed. */
export async function loadLocaleResources(): Promise<
  Record<string, Record<string, unknown>>
> {
  return {};
}
