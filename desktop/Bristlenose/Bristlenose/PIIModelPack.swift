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

    /// UserDefaults key holding the path of the acquired pack's **inner**
    /// versioned directory (`…/en_core_web_lg-<version>/`), written by
    /// whichever acquirer fetched it. Both channels converge here — managed
    /// Background Assets stores `url(for:).path` after
    /// `ensureLocalAvailability`, the `.dmg` stores its unpack destination — so
    /// the spawn-time handoff stays synchronous and asks one question of one
    /// key. Absent or empty means no pack has arrived.
    static let packDirectoryDefaultsKey = "piiModelPackDirectory"

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
            packDirectory: acquiredPackDirectory(defaults: defaults)
        )
    }

    /// Where an acquired pack sits, or `nil` if none has arrived.
    ///
    /// Reads the path an acquirer stored under `packDirectoryDefaultsKey`.
    /// Deliberately **not** liveness-checked here — `packEnvironment` applies
    /// the `meta.json` + `config.cfg` rule, and one site owning that rule is
    /// the point. A stored path whose directory has since gone (the system
    /// reclaimed a Background Assets pack under storage pressure, which it may)
    /// therefore yields the enabled flag alone, and stage 7 fails loudly with
    /// `MISSING_DEP` rather than the run proceeding unredacted.
    ///
    /// **The acquirers that write this key are still unwritten** (Phase 4b).
    /// Until one lands, nothing sets it and this returns `nil` on every
    /// machine — which is the safe answer, for the reason above.
    static func acquiredPackDirectory(
        defaults: UserDefaults = .standard
    ) -> URL? {
        guard let path = defaults.string(forKey: packDirectoryDefaultsKey),
              !path.isEmpty else { return nil }
        return URL(fileURLWithPath: path)
    }
}
