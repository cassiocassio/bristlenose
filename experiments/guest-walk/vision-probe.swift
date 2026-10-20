// vision-probe <image.png> — the control for "does Vision OCR work in this guest?".
// Unsandboxed, accurate level, same as the app's engine asks for. Prints the
// recognised lines, or the error. Separates a VM limit from an app problem.
import Foundation
import Vision

let url = URL(fileURLWithPath: CommandLine.arguments[1])
let req = VNRecognizeTextRequest()
req.recognitionLevel = .accurate
do {
    try VNImageRequestHandler(url: url).perform([req])
    let lines = (req.results ?? []).compactMap { $0.topCandidates(1).first?.string }
    print("ok: \(lines.count) lines")
    lines.prefix(5).forEach { print("  \($0)") }
} catch {
    print("error: \(error)")
    exit(1)
}
