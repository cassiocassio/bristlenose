import AppKit
import Foundation
import os

/// Reads the decorative `shoal-feed.jsonl` the pipeline writes during a
/// desktop-hosted run (`bristlenose/shoal_feed.py`) and turns each batch into
/// styled `WordPool.Word`s for the flock.
///
/// The file is small — truncated at run start, then a handful of append-only
/// batches (`word` / `theme` / `sentiment`) — so it's read *whole* each poll
/// rather than tailed. That sidesteps the growing-stream cursor pitfalls the
/// events reader has to handle, and re-reading is idempotent (the pool is
/// de-duped by text).
///
/// Purely decorative: a missing / empty / broken feed yields an empty pool and
/// the scene falls back to the canned `WordPool`. A single WARNING fires if the
/// file is present but stays empty (a stale bundled sidecar predating the emit —
/// otherwise the canned fallback would look identical to success at QA time).
enum ShoalFeed {
    private static let logger = Logger(subsystem: "app.bristlenose", category: "shoal")

    static let filename = "shoal-feed.jsonl"

    /// `<project>/bristlenose-output/.bristlenose/shoal-feed.jsonl` — mirrors
    /// `PipelineRunner.eventsURL(for:)`, read under the project's existing
    /// security-scoped access (same dir the events reader already reads).
    static func feedURL(projectPath: String) -> URL {
        URL(fileURLWithPath: projectPath)
            .appendingPathComponent("bristlenose-output")
            .appendingPathComponent(".bristlenose")
            .appendingPathComponent(filename)
    }

    private struct Batch: Decodable {
        let kind: String
        let texts: [String]
        let sentiment: String?
    }

    /// Read the whole feed and map every batch to a styled word. Empty on a
    /// missing file or no decodable batches. De-duped by text, preserving
    /// first-seen order (word batches arrive first, then themes, then sentiment).
    static func read(at url: URL) -> [WordPool.Word] {
        guard let data = try? Data(contentsOf: url), !data.isEmpty,
              let text = String(data: data, encoding: .utf8) else {
            return []
        }
        let decoder = JSONDecoder()
        var seen = Set<String>()
        var words: [WordPool.Word] = []
        for line in text.split(separator: "\n", omittingEmptySubsequences: true) {
            // Skip a malformed / half-written final line, keep the rest.
            let cleaned = line.trimmingCharacters(in: CharacterSet(charactersIn: "\0\r"))
            guard !cleaned.isEmpty, let lineData = cleaned.data(using: .utf8),
                  let batch = try? decoder.decode(Batch.self, from: lineData) else {
                continue
            }
            for raw in batch.texts {
                let word = raw.trimmingCharacters(in: .whitespacesAndNewlines)
                guard !word.isEmpty, seen.insert(word).inserted else { continue }
                words.append(styled(word, kind: batch.kind, sentiment: batch.sentiment))
            }
        }
        return words
    }

    /// One-shot WARNING when the feed exists but never populates — converts a
    /// stale-sidecar silent-canned-fallback into a greppable tell.
    static func logStaleEmpty(at url: URL, serverVersion: String?) {
        logger.warning(
            "shoal feed present but no batches — stale sidecar? serving=\(serverVersion ?? "?", privacy: .public)"
        )
    }

    private static func styled(_ text: String, kind: String, sentiment: String?) -> WordPool.Word {
        switch kind {
        case "theme":
            return WordPool.Word(text: text, fontSize: 13, color: .labelColor.withAlphaComponent(0.7))
        case "sentiment":
            return WordPool.Word(text: text, fontSize: 15, color: sentimentColor(sentiment))
        default:  // "word"
            return WordPool.Word(text: text, fontSize: 11, color: .labelColor.withAlphaComponent(0.5))
        }
    }

    private static func sentimentColor(_ sentiment: String?) -> NSColor {
        switch sentiment {
        case "positive": return ShoalSentiment.positive.color
        case "negative": return ShoalSentiment.negative.color
        default: return ShoalSentiment.neutral.color
        }
    }
}
