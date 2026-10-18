// Does SpeechTranscriber work inside the App Sandbox, with no network entitlement?
// Reads a 16 kHz WAV from stdin (a sandboxed process cannot open the repo's
// files), writes it to its own container's tmp, fetches the locale's model if
// needed, transcribes, and prints one JSON line. Signed ad hoc with
// sandbox.entitlements (app-sandbox only):
//
//   swiftc -parse-as-library -O sandbox_probe.swift -o sbprobe
//   codesign -f -s - --entitlements sandbox.entitlements sbprobe
//   ./sbprobe <locale> < audio.wav
import AVFoundation
import Foundation
import Speech

func emit(_ d: [String: Any]) {
    let data = try! JSONSerialization.data(withJSONObject: d, options: [.sortedKeys])
    print(String(data: data, encoding: .utf8)!)
}

@main
struct SandboxProbe {
    static func main() async {
        var out: [String: Any] = [:]
        out["home"] = NSHomeDirectory()
        out["sandboxed"] = ProcessInfo.processInfo.environment["APP_SANDBOX_CONTAINER_ID"] != nil
        // The real home (not the container): a sandboxed process must not be able to list it.
        let realHome = String(cString: getpwuid(getuid())!.pointee.pw_dir)
        out["can_list_real_home"] = (try? FileManager.default.contentsOfDirectory(atPath: realHome + "/Documents")) != nil
        out["speech_auth"] = "\(SFSpeechRecognizer.authorizationStatus().rawValue)"
        let loc = Locale(identifier: CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "en-GB")
        let data = FileHandle.standardInput.readDataToEndOfFile()
        let wav = URL(fileURLWithPath: NSTemporaryDirectory()).appendingPathComponent("probe.wav")
        do { try data.write(to: wav) } catch { out["error"] = "write: \(error)"; emit(out); return }
        guard let eq = await SpeechTranscriber.supportedLocale(equivalentTo: loc) else {
            out["error"] = "unsupported"; emit(out); return
        }
        let t = SpeechTranscriber(locale: eq, preset: .timeIndexedTranscriptionWithAlternatives)
        out["status_before"] = "\(await AssetInventory.status(forModules: [t]))"
        let ti = Date()
        do {
            if let req = try await AssetInventory.assetInstallationRequest(supporting: [t]) {
                try await req.downloadAndInstall()
            }
        } catch { out["error"] = "install: \(error)"; emit(out); return }
        out["install_s"] = Date().timeIntervalSince(ti)
        out["status_after"] = "\(await AssetInventory.status(forModules: [t]))"
        do {
            let file = try AVAudioFile(forReading: wav)
            let analyzer = SpeechAnalyzer(modules: [t])
            async let text: String = {
                var s = ""
                for try await r in t.results where r.isFinal { s += String(r.text.characters) }
                return s
            }()
            if let last = try await analyzer.analyzeSequence(from: file) {
                try await analyzer.finalizeAndFinish(through: last)
            }
            let s = try await text
            out["chars"] = s.count
            out["words"] = s.split(separator: " ").count
        } catch { out["error"] = "analyse: \(error)" }
        _ = await AssetInventory.release(reservedLocale: eq)
        emit(out)
    }
}
