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
}
