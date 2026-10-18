// Transcribe one audio file with Apple's on-device speech framework and write the
// result as JSON: segments (one per final result), words (one per attributed run,
// with time range and confidence), and timings.
//
//   swiftc -parse-as-library -O transcribe.swift -o transcribe
//   ./transcribe <audio> <locale> <out.json> [--engine speech|dictation] [--install]
//
// --engine speech     SpeechTranscriber (new in macOS 26), preset with time ranges
// --engine dictation  DictationTranscriber (the older dictation model, more locales),
//                     long-dictation preset with punctuation and time ranges
// --context FILE      supply the words in FILE (one per line) as contextualStrings
// --install           fetch the locale's model if it is not on the Mac (timed);
//                     without it, a missing model is reported and nothing is fetched
//
//   ./transcribe --list              this tool's reserved locales, installed locales
//   ./transcribe --release <locale>  release one reservation (the public, reversible
//                                    API; at most 5 locales can be reserved at once,
//                                    and reservations belong to the executable)
//
// Experiment only; nothing here is product code.
import AVFoundation
import Foundation
import Speech

struct Word: Encodable { let start: Double; let end: Double; let text: String; let conf: Double? }
struct Segment: Encodable { let start: Double; let end: Double; let text: String }
struct Output: Encodable {
    let engine: String
    let locale: String
    let audio_s: Double
    let status_before: String
    let install_s: Double?
    let prepare_s: Double
    let analyse_s: Double
    let wall_s: Double
    let segments: [Segment]
    let words: [Word]
}

func secs(_ t: CMTime) -> Double { t.isNumeric ? t.seconds : .nan }

func fail(_ msg: String) -> Never {
    FileHandle.standardError.write((msg + "\n").data(using: .utf8)!)
    exit(2)
}

@main
struct Transcribe {
    static func main() async {
        var args = Array(CommandLine.arguments.dropFirst())
        if args.first == "--list" {
            print("maximumReservedLocales", AssetInventory.maximumReservedLocales)
            print("reserved", await AssetInventory.reservedLocales.map { $0.identifier(.bcp47) })
            print("SpeechTranscriber installed",
                  await SpeechTranscriber.installedLocales.map { $0.identifier(.bcp47) }.sorted())
            print("DictationTranscriber installed",
                  await DictationTranscriber.installedLocales.map { $0.identifier(.bcp47) }.sorted())
            return
        }
        if args.first == "--release", args.count == 2 {
            // Match on BCP 47: Locale("de-DE") is not equal to the stored de_DE.
            let held = await AssetInventory.reservedLocales.filter { $0.identifier(.bcp47) == args[1] }
            for loc in held { print("release", args[1], await AssetInventory.release(reservedLocale: loc)) }
            if held.isEmpty { print("release", args[1], "not reserved") }
            return
        }
        var engine = "speech"
        var install = false
        if let i = args.firstIndex(of: "--engine") { engine = args[i + 1]; args.removeSubrange(i...i + 1) }
        if let i = args.firstIndex(of: "--install") { install = true; args.remove(at: i) }
        var vocab: [String] = []
        if let i = args.firstIndex(of: "--context") {
            vocab = ((try? String(contentsOfFile: args[i + 1], encoding: .utf8)) ?? "")
                .split(separator: "\n").map(String.init).filter { !$0.isEmpty }
            args.removeSubrange(i...i + 1)
        }
        guard args.count == 3 else { fail("usage: transcribe <audio> <locale> <out.json> [--engine speech|dictation] [--install]") }
        let url = URL(fileURLWithPath: args[0])
        let wanted = Locale(identifier: args[1])
        let outURL = URL(fileURLWithPath: args[2])
        let t0 = Date()

        let module: any SpeechModule
        let locale: Locale
        if engine == "speech" {
            guard let eq = await SpeechTranscriber.supportedLocale(equivalentTo: wanted) else {
                fail("unsupported locale for SpeechTranscriber: \(wanted.identifier)")
            }
            locale = eq
            module = SpeechTranscriber(locale: eq, transcriptionOptions: [], reportingOptions: [],
                                       attributeOptions: [.audioTimeRange, .transcriptionConfidence])
        } else if engine == "dictation-preset" || engine == "dictation-ff" {
            guard let eq = await DictationTranscriber.supportedLocale(equivalentTo: wanted) else {
                fail("unsupported locale for DictationTranscriber: \(wanted.identifier)")
            }
            locale = eq
            if engine == "dictation-preset" {
                // Apple's own preset for long, time-indexed dictation.
                module = DictationTranscriber(locale: eq, preset: .timeIndexedLongDictation)
            } else {
                // Finalise often, so long input is not held in one growing result.
                module = DictationTranscriber(locale: eq, contentHints: [], transcriptionOptions: [.punctuation],
                                              reportingOptions: [.frequentFinalization],
                                              attributeOptions: [.audioTimeRange, .transcriptionConfidence])
            }
        } else {
            guard let eq = await DictationTranscriber.supportedLocale(equivalentTo: wanted) else {
                fail("unsupported locale for DictationTranscriber: \(wanted.identifier)")
            }
            locale = eq
            module = DictationTranscriber(locale: eq, contentHints: [], transcriptionOptions: [.punctuation],
                                          reportingOptions: [],
                                          attributeOptions: [.audioTimeRange, .transcriptionConfidence])
        }

        let before = await AssetInventory.status(forModules: [module])
        var installSecs: Double? = nil
        if before != .installed {
            if !install { fail("model not installed for \(locale.identifier) (status \(before)); rerun with --install") }
            let ti = Date()
            do {
                if let req = try await AssetInventory.assetInstallationRequest(supporting: [module]) {
                    let p = req.progress
                    let obs = p.observe(\.fractionCompleted) { pr, _ in
                        FileHandle.standardError.write(String(format: "install %.0f%% (%lld/%lld)\n",
                            pr.fractionCompleted * 100, pr.completedUnitCount, pr.totalUnitCount).data(using: .utf8)!)
                    }
                    try await req.downloadAndInstall()
                    obs.invalidate()
                }
            } catch { fail("install failed: \(error)") }
            installSecs = Date().timeIntervalSince(ti)
        }

        let file: AVAudioFile
        do { file = try AVAudioFile(forReading: url) } catch { fail("cannot open audio: \(error)") }
        let audioSecs = Double(file.length) / file.processingFormat.sampleRate

        let analyzer = SpeechAnalyzer(modules: [module])
        if !vocab.isEmpty {
            let ctx = AnalysisContext()
            ctx.contextualStrings[.general] = vocab
            do { try await analyzer.setContext(ctx) } catch { fail("context failed: \(error)") }
        }
        let tp = Date()
        do {
            let fmt = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [module])
            try await analyzer.prepareToAnalyze(in: fmt)
        } catch { fail("prepare failed: \(error)") }
        let prepareSecs = Date().timeIntervalSince(tp)

        var segments: [Segment] = []
        var words: [Word] = []
        func collect(_ text: AttributedString, _ range: CMTimeRange) {
            let plain = String(text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
            if !plain.isEmpty {
                segments.append(Segment(start: secs(range.start), end: secs(range.end), text: plain))
            }
            for run in text.runs {
                let w = String(text[run.range].characters)
                if w.trimmingCharacters(in: .whitespaces).isEmpty { continue }
                if let tr = run.audioTimeRange {
                    words.append(Word(start: secs(tr.start), end: secs(tr.end), text: w,
                                      conf: run.transcriptionConfidence))
                }
            }
        }

        let ta = Date()
        do {
            if let st = module as? SpeechTranscriber {
                async let gathered: [(AttributedString, CMTimeRange)] = {
                    var acc: [(AttributedString, CMTimeRange)] = []
                    for try await r in st.results where r.isFinal { acc.append((r.text, r.range)) }
                    return acc
                }()
                if let last = try await analyzer.analyzeSequence(from: file) {
                    try await analyzer.finalizeAndFinish(through: last)
                } else { await analyzer.cancelAndFinishNow() }
                for (t, r) in try await gathered { collect(t, r) }
            } else if let dt = module as? DictationTranscriber {
                async let gathered: [(AttributedString, CMTimeRange)] = {
                    var acc: [(AttributedString, CMTimeRange)] = []
                    for try await r in dt.results where r.isFinal { acc.append((r.text, r.range)) }
                    return acc
                }()
                if let last = try await analyzer.analyzeSequence(from: file) {
                    try await analyzer.finalizeAndFinish(through: last)
                } else { await analyzer.cancelAndFinishNow() }
                for (t, r) in try await gathered { collect(t, r) }
            }
        } catch { fail("analysis failed: \(error)") }
        let analyseSecs = Date().timeIntervalSince(ta)

        let out = Output(engine: engine, locale: locale.identifier(.bcp47), audio_s: audioSecs,
                         status_before: "\(before)", install_s: installSecs, prepare_s: prepareSecs,
                         analyse_s: analyseSecs, wall_s: Date().timeIntervalSince(t0),
                         segments: segments, words: words)
        let enc = JSONEncoder()
        enc.outputFormatting = [.prettyPrinted, .withoutEscapingSlashes]
        do { try enc.encode(out).write(to: outURL) } catch { fail("cannot write: \(error)") }
        print(String(format: "%@ %@ audio %.0fs analyse %.1fs RTF %.4f segments %d words %d",
                     engine, locale.identifier(.bcp47), audioSecs, analyseSecs, analyseSecs / audioSecs,
                     segments.count, words.count))
    }
}
