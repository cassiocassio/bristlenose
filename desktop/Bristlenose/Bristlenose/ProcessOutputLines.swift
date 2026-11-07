import Foundation

/// Frame process output as bytes: a pipe read is neither a line nor a UTF-8 boundary.
struct ProcessOutputLines {
    private var pending = Data()

    mutating func append(_ chunk: Data) -> [String] {
        pending.append(chunk)
        var lines: [String] = []
        while let newline = pending.firstIndex(of: 10) {
            let bytes = pending[..<newline]
            if let line = String(data: bytes, encoding: .utf8), !line.isEmpty {
                lines.append(line)
            }
            pending.removeSubrange(...newline)
        }
        return lines
    }

    mutating func finish() -> String? {
        defer { pending.removeAll() }
        guard !pending.isEmpty else { return nil }
        return String(data: pending, encoding: .utf8)
    }

    /// Every line the pipe will carry, in order, read on a thread of its own; the stream
    /// finishes at EOF, which comes when the process exits.
    ///
    /// Not a `Task.detached`: a pipe read waits in the kernel until the process writes or
    /// exits, and a thread waiting there is one the cooperative pool cannot reuse, so each
    /// live sidecar held a pool thread for its whole life. With a serve per open study, a
    /// run and a standby, a Mac with as many sidecars as cores had every other continuation
    /// in the app queued behind them; the Swift suite's `/bin/sh` stand-ins did the same on
    /// the 3-core runners and a standby's ready line went unread (6 Nov 2026,
    /// `PoolStarvationTimeoutTests.aPipeReaderHoldsNoPoolThread`).
    static func lines(from handle: FileHandle) -> AsyncStream<String> {
        let (stream, continuation) = AsyncStream<String>.makeStream()
        Thread.detachNewThread {
            var framer = ProcessOutputLines()
            while true {
                let data = handle.availableData
                if data.isEmpty {
                    if let last = framer.finish() { continuation.yield(last) }
                    break
                }
                for line in framer.append(data) { continuation.yield(line) }
            }
            continuation.finish()
        }
        return stream
    }
}
