import Foundation

/// Where the PII detection model lives on this Mac, and how the sidecar is told.
///
/// The detection *code* (presidio + spaCy, 33 MB measured) ships inside the
/// reviewed binary. Only the ~425 MB `en_core_web_lg` **weights** are acquired
/// on demand, which is what keeps this on the clean side of App Store §2.5.2 —
/// a model is data, and the pack contains zero `.py` files (measured).
///
/// This type is the **handoff half** of that delivery: given a pack that has
/// arrived, it tells the Python side where to look. It deliberately does not
/// acquire anything. The acquirers are per-channel and land separately:
///
///   - `.appStoreOrTestFlight` — managed Background Assets
///     (`AssetPackManager.ensureLocalAvailabilityOfAssetPack`), macOS 26+,
///     which is why Mac PII is gated at 26 rather than the app floor moving.
///   - `.developerID` — plain HTTPS from bristlenose.app/models/, SHA-256
///     pinned.
///   - the CLI is not this app's problem: `spacy download` installs an
///     importable package and never sets the variable below.
///
/// Everything downstream of `packEnvironment` is already built and measured:
/// stage 7, `bristlenose doctor` and the Pipeline view all resolve through
/// Python's `resolve_spacy_model()`, and the path route was verified to score
/// identically to the package route with the package made unimportable.
enum PIIModelPack {

    /// UserDefaults key behind Settings ▸ Privacy. Absent means off, which is
    /// the intended default — redaction is opt-in.
    static let enabledDefaultsKey = "piiEnabled"

    /// The two files spaCy needs, in the order **it** reads them.
    ///
    /// `load_model_from_path` calls `get_model_meta` (meta.json) before it
    /// reads config.cfg, so checking only config.cfg lets a half-unpacked
    /// directory through that then dies inside spaCy with an opaque
    /// `E053: Could not read meta.json`. Python's `resolve_spacy_model()`
    /// applies the identical pair; this is the Swift mirror of that check, and
    /// the two must not drift.
    static let requiredFiles = ["meta.json", "config.cfg"]

    /// Is `directory` a loadable spaCy model directory?
    ///
    /// Note this must be the **inner** versioned directory — for
    /// `en_core_web_lg` that is `en_core_web_lg-<version>/`, not its parent.
    /// Pointing one level too high is the single commonest way to get this
    /// wrong, and it is what `bristlenose doctor` now says out loud rather
    /// than reporting an incompatible Python.
    static func isLoadableModelDirectory(
        _ directory: URL,
        fileManager: FileManager = .default
    ) -> Bool {
        requiredFiles.allSatisfy { name in
            fileManager.fileExists(
                atPath: directory.appendingPathComponent(name).path
            )
        }
    }

    /// The environment the sidecar needs for redaction.
    ///
    /// Two variables, and the asymmetry between them is deliberate:
    ///
    /// - `BRISTLENOSE_PII_ENABLED` is set whenever the researcher asked for
    ///   redaction, **even when no pack has arrived**. Withholding it would be
    ///   the worse failure: they asked for redaction, the run would proceed
    ///   without it, and nothing would say so. Stage 7 instead abandons the run
    ///   with a `MISSING_DEP` cause — loud, classified, and rendered on the
    ///   project row. That resolves the "a run starts before the download
    ///   finishes" question in favour of failing cleanly, which became nearly
    ///   free once the stage-7 failure apparatus landed.
    ///
    /// - `BRISTLENOSE_PII_MODEL_DIR` is set **only** when a loadable pack is
    ///   actually present. Pointing it at a directory that is missing or
    ///   half-unpacked makes Python's resolver raise by design rather than
    ///   silently falling back to the package name — and that fallback is not
    ///   cosmetic: Presidio's engine builder shells out to `pip install` from
    ///   GitHub for a name it cannot resolve, which inside a sandboxed App
    ///   Store binary is a §2.5.2 violation.
    ///
    /// Returns an empty dictionary when redaction is off, so the sidecar's
    /// environment is untouched on the overwhelmingly common path.
    static func packEnvironment(
        enabled: Bool,
        packDirectory: URL?,
        fileManager: FileManager = .default
    ) -> [String: String] {
        guard enabled else { return [:] }

        var env = ["BRISTLENOSE_PII_ENABLED": "1"]
        if let directory = packDirectory,
           isLoadableModelDirectory(directory, fileManager: fileManager) {
            env["BRISTLENOSE_PII_MODEL_DIR"] = directory.path
        }
        return env
    }

    /// The same, read from live app state.
    ///
    /// `packDirectory` is `nil` until an acquirer exists, so today this yields
    /// at most the enabled flag — and a researcher who switches redaction on
    /// gets an honest failed run rather than a quietly unredacted one.
    static func currentEnvironment(
        defaults: UserDefaults = .standard
    ) -> [String: String] {
        packEnvironment(
            enabled: defaults.bool(forKey: enabledDefaultsKey),
            packDirectory: acquiredPackDirectory()
        )
    }

    /// Where an acquired pack sits, or `nil` if none has arrived.
    ///
    /// **This is the seam the acquirers fill**, and the only part of PII
    /// delivery still unwritten. Managed Background Assets hands back its own
    /// URL rather than depositing at a path we choose, so this cannot be a
    /// hardcoded container path for that channel — it must ask
    /// `AssetPackManager`. The Developer-ID `.dmg` downloads to a location it
    /// picks and can answer from disk.
    ///
    /// Returning `nil` is correct and safe today: redaction fails loudly
    /// instead of running unredacted.
    static func acquiredPackDirectory() -> URL? {
        nil
    }
}
