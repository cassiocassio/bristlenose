import Foundation
import Testing

@testable import Bristlenose

// **Nested inside `CloudTransportTests`, and `.serialized`**, for the reason
// `GrantLifecycleTests` records: `StubURLProtocol` is process-wide state, and a
// parallel suite that enqueues into it gets another suite's queue.
extension CloudTransportTests {

/// `/api/pull` streams `application/x-ndjson`. Once the 200 has gone out Ollama
/// reports a failure (a full disk, an older daemon that does not know the model,
/// a dropped registry) as one `{"error": …}` line and ends the stream. The reader
/// ignored it, the loop finished normally, and the pill read it as a download
/// that worked, so the first analysis failed with "model not found" (N163).
@Suite("Ollama pull stream", .serialized)
@MainActor
struct OllamaPullStreamTests {

    private let base = URL(string: "http://127.0.0.1:11434")!

    private func stream(_ lines: String) {
        StubURLProtocol.reset()
        StubURLProtocol.enqueue(StubURLProtocol.Stub(
            status: 200,
            headers: ["Content-Type": "application/x-ndjson"],
            body: Data(lines.utf8)))
    }

    private func pull() async throws -> [LLMValidator.PullProgress] {
        let box = ProgressBox()
        try await LLMValidator.pullModel(
            tag: "gemma4:e4b", baseURL: base, session: StubURLProtocol.session()
        ) { progress in box.add(progress) }
        return box.all
    }

    private final class ProgressBox {
        private(set) var all: [LLMValidator.PullProgress] = []
        func add(_ p: LLMValidator.PullProgress) { all.append(p) }
    }

    @Test("A stream that ends with an error line is a failed pull")
    func errorLineFails() async {
        stream("""
        {"status":"pulling manifest"}
        {"status":"pulling abc","digest":"sha256:abc","total":100,"completed":40}
        {"error":"write /root/.ollama/models/blobs: no space left on device"}

        """)

        do {
            _ = try await pull()
            Issue.record("the pull returned normally: the pill would read it as downloaded")
        } catch let failure as LLMValidator.OllamaPullError {
            #expect(failure.message.contains("no space left"),
                    "the daemon's own words reach the pill's failure")
            // ...and the pill shows them as its generic failure, not Foundation's
            // "The operation couldn't be completed".
            #expect(OllamaDownloadModel.classify(failure) == .generic(failure.message))
        } catch {
            Issue.record("the wrong kind of failure: \(error)")
        }
    }

    @Test("An error line with no newline after it still fails the pull")
    func unterminatedErrorLine() async {
        stream(#"{"status":"pulling manifest"}"# + "\n" + #"{"error":"model not found"}"#)

        do {
            _ = try await pull()
            Issue.record("an unterminated last line was never read")
        } catch let failure as LLMValidator.OllamaPullError {
            #expect(failure.message == "model not found")
        } catch {
            Issue.record("the wrong kind of failure: \(error)")
        }
    }

    @Test("A stream that finishes with success is a finished pull, and progress is reported")
    func successLineFinishes() async throws {
        stream("""
        {"status":"pulling manifest"}
        {"status":"pulling abc","digest":"sha256:abc","total":100,"completed":100}
        {"status":"success"}

        """)

        let seen = try await pull()

        #expect(seen.count == 3)
        #expect(seen.last?.statusLine == "success")
        #expect(seen.contains { $0.completedBytes == 100 && $0.totalBytes == 100 })
    }

    @Test("An empty error string is not a failure")
    func emptyErrorIsNotAFailure() async throws {
        stream(#"{"status":"pulling manifest","error":""}"# + "\n")
        let seen = try await pull()
        #expect(seen.count == 1)
    }
}

}
