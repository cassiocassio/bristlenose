// macOS 27: transcribe straight from a video file's audio track
// (AssetInputSequenceProvider), with no ffmpeg extraction, and time it.
//   swiftc -parse-as-library -O video_probe.swift -o video_probe
//   ./video_probe <video> <locale>
import AVFoundation
import Foundation
import Speech

@main
struct VideoProbe {
    static func main() async throws {
        let args = CommandLine.arguments
        let asset = AVURLAsset(url: URL(fileURLWithPath: args[1]))
        guard let track = try await asset.loadTracks(withMediaType: .audio).first else {
            print("no audio track"); return
        }
        let t = SpeechTranscriber(locale: Locale(identifier: args[2]), transcriptionOptions: [],
                                  reportingOptions: [], attributeOptions: [.audioTimeRange])
        guard let fmt = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [t]) else {
            print("no format"); return
        }
        let provider = AssetInputSequenceProvider(asset: asset, track: track, analyzerFormat: fmt)
        let analyzer = SpeechAnalyzer(modules: [t])
        let t0 = Date()
        async let text: [String] = {
            var acc: [String] = []
            for try await r in t.results where r.isFinal { acc.append(String(r.text.characters)) }
            return acc
        }()
        if let last = try await analyzer.analyzeSequence(provider.analyzerInputs) {
            try await analyzer.finalizeAndFinish(through: last)
        } else { await analyzer.cancelAndFinishNow() }
        let segs = try await text
        let words = segs.joined(separator: " ").split(separator: " ").count
        print(String(format: "video input: %d segments, %d words, %.1f s", segs.count, words,
                     Date().timeIntervalSince(t0)))
    }
}
