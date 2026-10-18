// bristlenose-speech: transcribe one WAV with Apple's on-device SpeechTranscriber
// (docs/design-apple-first-transcription.md §3 A).
//
//   bristlenose-speech probe
//   bristlenose-speech transcribe <wav> <bcp47-locale> <out.json>
//
// The bundled sidecar launches it, so it runs inside the app's sandbox
// (app-sandbox + inherit, no network: the model fetch is done by a system
// daemon). The JSON it writes is a contract with bristlenose/apple_speech.py,
// held by tests/fixtures/apple-speech/helper-output.json, which both sides read.
//
// Exit codes: 0 done; 2 usage or failure (message on stderr); 3 unavailable
// (below macOS 26, or SpeechTranscriber not available on this Mac); 4 locale
// not supported; 5 model not installed and the fetch failed. While analysing,
// stderr carries `@progress <seconds_done> <audio_s>` lines.
//
// Built for the app's 15.0 floor; everything Speech is behind
// `if #available(macOS 26, *)`. Built and signed by build-helper.sh.
import AVFoundation
import Darwin
import Foundation
import Speech

let SCHEMA = 1
let OS_VERSION = ProcessInfo.processInfo.operatingSystemVersionString

// FileHandle writes are unbuffered write(2) calls: a line reaches the reader
// when it is written, which is what @progress needs.
func emitStderr(_ s: String) { FileHandle.standardError.write(Data((s + "\n").utf8)) }

func fail(_ code: Int32, _ msg: String) -> Never {
    emitStderr("bristlenose-speech: " + msg)
    exit(code)
}

let USAGE = "usage: bristlenose-speech probe | bristlenose-speech transcribe <wav> <bcp47-locale> <out.json>"

// MARK: - JSON shapes (schema 1). Optionals encode as null, never omitted.
// Keys are written sorted: this Foundation's JSONEncoder does not keep
// declaration order, and sorted output is at least the same every run.

struct Probe: Encodable {
    let available: Bool
    let reason: String?
    let supported: [String]
    let installed: [String]
    enum K: String, CodingKey { case schema, available, reason, os_version, supported, installed }
    func encode(to e: Encoder) throws {
        var c = e.container(keyedBy: K.self)
        try c.encode(SCHEMA, forKey: .schema)
        try c.encode(available, forKey: .available)
        try c.encode(reason, forKey: .reason)
        try c.encode(OS_VERSION, forKey: .os_version)
        try c.encode(supported, forKey: .supported)
        try c.encode(installed, forKey: .installed)
    }
}

struct Word: Encodable {
    let start: Double
    let end: Double
    let text: String
    let conf: Double?
    enum K: String, CodingKey { case start, end, text, conf }
    func encode(to e: Encoder) throws {
        var c = e.container(keyedBy: K.self)
        try c.encode(start, forKey: .start)
        try c.encode(end, forKey: .end)
        try c.encode(text, forKey: .text)
        try c.encode(conf, forKey: .conf)
    }
}

struct ResultOut: Encodable {
    let start: Double
    let end: Double
    let text: String
    let words: [Word]
}

struct Output: Encodable {
    let locale: String
    let audio_s: Double
    let install_s: Double?
    let analyse_s: Double
    let results: [ResultOut]
    enum K: String, CodingKey {
        case schema, engine, locale, asset_version, os_version, audio_s, install_s, analyse_s, results
    }
    func encode(to e: Encoder) throws {
        var c = e.container(keyedBy: K.self)
        try c.encode(SCHEMA, forKey: .schema)
        try c.encode("speech-transcriber", forKey: .engine)
        try c.encode(locale, forKey: .locale)
        // No public API reports the model asset's version, and the helper
        // reads no private paths, so this stays null (allowed by the contract).
        try c.encode(String?.none, forKey: .asset_version)
        try c.encode(OS_VERSION, forKey: .os_version)
        try c.encode(audio_s, forKey: .audio_s)
        try c.encode(install_s, forKey: .install_s)
        try c.encode(analyse_s, forKey: .analyse_s)
        try c.encode(results, forKey: .results)
    }
}

/// Seconds, or nil for an invalid or indefinite time (JSON has no NaN).
func secs(_ t: CMTime) -> Double? {
    guard t.isNumeric else { return nil }
    let s = t.seconds
    return s.isFinite ? s : nil
}

func bcp47(_ l: Locale) -> String { l.identifier(.bcp47) }

/// Write JSON to a temp file beside `url`, then rename(2) it into place, so a
/// reader never sees a half-written file.
func writeAtomically(_ data: Data, to url: URL) {
    let tmp = url.deletingLastPathComponent()
        .appendingPathComponent(".\(url.lastPathComponent).\(getpid()).tmp")
    do { try data.write(to: tmp) } catch { fail(2, "cannot write \(tmp.path): \(error)") }
    if rename(tmp.path, url.path) != 0 {
        let err = String(cString: strerror(errno))
        unlink(tmp.path)
        fail(2, "cannot move the result into place at \(url.path): \(err)")
    }
}

// MARK: - probe

func probe() async {
    var p = Probe(available: false, reason: "requires macOS 26 or later", supported: [], installed: [])
    if #available(macOS 26, *) {
        if SpeechTranscriber.isAvailable {
            p = Probe(available: true, reason: nil,
                      supported: await SpeechTranscriber.supportedLocales.map(bcp47).sorted(),
                      installed: await SpeechTranscriber.installedLocales.map(bcp47).sorted())
        } else {
            p = Probe(available: false, reason: "SpeechTranscriber is not available on this Mac",
                      supported: [], installed: [])
        }
    }
    let enc = JSONEncoder()
    enc.outputFormatting = [.sortedKeys, .withoutEscapingSlashes]
    guard let data = try? enc.encode(p) else { fail(2, "cannot encode the probe") }
    FileHandle.standardOutput.write(data + Data("\n".utf8))
}

// MARK: - transcribe

@available(macOS 26, *)
func collect(_ r: SpeechTranscriber.Result) -> ResultOut? {
    let text = r.text
    var words: [Word] = []
    for run in text.runs {
        let w = String(text[run.range].characters)
        if w.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { continue }
        guard let tr = run.audioTimeRange, let s = secs(tr.start), let e = secs(tr.end) else { continue }
        let conf = run.transcriptionConfidence.flatMap { $0.isFinite ? $0 : nil }
        words.append(Word(start: s, end: e, text: w, conf: conf))
    }
    let plain = String(text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
    if plain.isEmpty && words.isEmpty { return nil }
    guard let start = secs(r.range.start) ?? words.first?.start,
          let end = secs(r.range.end) ?? words.last?.end else { return nil }
    return ResultOut(start: start, end: end, text: plain, words: words)
}

/// Release every reservation this executable holds for `locale`. Matched on
/// BCP 47, because release only accepts the stored Locale object:
/// Locale("de-DE") is not equal to the stored de_DE and the call returns false
/// (experiments/apple-speech/README.md § Reservations).
@available(macOS 26, *)
func releaseReservation(_ locale: Locale) async {
    let want = bcp47(locale)
    for held in await AssetInventory.reservedLocales where bcp47(held) == want {
        if await !AssetInventory.release(reservedLocale: held) {
            emitStderr("bristlenose-speech: could not release the \(want) reservation")
        }
    }
}

@available(macOS 26, *)
func transcribe(wav: String, localeArg: String, out: String) async {
    guard SpeechTranscriber.isAvailable else { fail(3, "SpeechTranscriber is not available on this Mac") }
    let outURL = URL(fileURLWithPath: out)

    let file: AVAudioFile
    do { file = try AVAudioFile(forReading: URL(fileURLWithPath: wav)) } catch { fail(2, "cannot open audio \(wav): \(error)") }
    let sampleRate = file.processingFormat.sampleRate
    guard sampleRate > 0 else { fail(2, "audio has no sample rate: \(wav)") }
    let audioSecs = Double(file.length) / sampleRate

    guard let locale = await SpeechTranscriber.supportedLocale(equivalentTo: Locale(identifier: localeArg)) else {
        fail(4, "locale not supported by SpeechTranscriber: \(localeArg)")
    }
    let module = SpeechTranscriber(locale: locale, transcriptionOptions: [], reportingOptions: [],
                                   attributeOptions: [.audioTimeRange, .transcriptionConfidence])

    // Fetch the model if this executable has not got it. Status is per app:
    // `installed` means "reserved by this executable", so a model already on
    // the Mac still goes through the request, which then returns at once with
    // nothing fetched. install_s is recorded only when something was fetched.
    var installSecs: Double? = nil
    let before = await AssetInventory.status(forModules: [module])
    if before == .unsupported { fail(4, "no SpeechTranscriber model for \(bcp47(locale))") }
    if before != .installed {
        let onDisk = await SpeechTranscriber.installedLocales.contains { bcp47($0) == bcp47(locale) }
        let t0 = Date()
        do {
            if let req = try await AssetInventory.assetInstallationRequest(supporting: [module]) {
                if !onDisk { emitStderr("bristlenose-speech: fetching the \(bcp47(locale)) model") }
                try await req.downloadAndInstall()
                if !onDisk { installSecs = Date().timeIntervalSince(t0) }
            }
        } catch {
            await releaseReservation(locale)
            fail(5, "could not install the \(bcp47(locale)) model: \(error)")
        }
        let after = await AssetInventory.status(forModules: [module])
        if after != .installed {
            await releaseReservation(locale)
            fail(5, "the \(bcp47(locale)) model is not installed after the request (status \(after))")
        }
    }

    var results: [ResultOut] = []
    let analyseSecs: Double
    do {
        let analyzer = SpeechAnalyzer(modules: [module])
        let t0 = Date()
        let fmt = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [module])
        try await analyzer.prepareToAnalyze(in: fmt)
        emitStderr(String(format: "@progress %.2f %.2f", 0.0, audioSecs))
        async let gathered: [ResultOut] = {
            var acc: [ResultOut] = []
            for try await r in module.results where r.isFinal {
                guard let item = collect(r) else { continue }
                acc.append(item)
                emitStderr(String(format: "@progress %.2f %.2f", min(max(item.end, 0), audioSecs), audioSecs))
            }
            return acc
        }()
        if let last = try await analyzer.analyzeSequence(from: file) {
            try await analyzer.finalizeAndFinish(through: last)
        } else {
            await analyzer.cancelAndFinishNow()
        }
        results = try await gathered
        analyseSecs = Date().timeIntervalSince(t0)
    } catch {
        await releaseReservation(locale)
        fail(2, "analysis failed: \(error)")
    }

    await releaseReservation(locale)

    let enc = JSONEncoder()
    enc.outputFormatting = [.prettyPrinted, .sortedKeys, .withoutEscapingSlashes]
    let output = Output(locale: bcp47(locale), audio_s: audioSecs, install_s: installSecs,
                        analyse_s: analyseSecs, results: results)
    let data: Data
    do { data = try enc.encode(output) } catch { fail(2, "cannot encode the result: \(error)") }
    writeAtomically(data, to: outURL)
}

// MARK: - main

let args = Array(CommandLine.arguments.dropFirst())
switch args.first {
case "probe" where args.count == 1:
    await probe()
case "transcribe" where args.count == 4:
    if #available(macOS 26, *) {
        await transcribe(wav: args[1], localeArg: args[2], out: args[3])
    } else {
        fail(3, "SpeechTranscriber requires macOS 26 or later")
    }
default:
    fail(2, USAGE)
}
exit(0)
