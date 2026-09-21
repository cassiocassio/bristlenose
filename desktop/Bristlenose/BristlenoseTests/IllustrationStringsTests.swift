import Foundation
import Testing

@testable import Bristlenose

/// `WelcomeIllustrationHTML.stringsBlock` — the one place an illustration's
/// words cross into HTML.
///
/// The seam exists because a string reaching these templates has **four**
/// different escapes waiting for it and they disagree: a JS string literal, an
/// HTML text node, an attribute, and anything concatenated into `innerHTML`
/// inside the script. Nine templates times ~57 strings is not a set of decisions
/// worth making one at a time, so they cross once, as JSON, and are read back
/// through `textContent`, which parses nothing.
///
/// These strings are about to become translations — authored per locale, by
/// people, in twenty-one languages. That is the moment a `</script>` or an
/// ampersand stops being hypothetical.
@Suite("WelcomeIllustrationHTML.stringsBlock")
struct IllustrationStringsTests {

    private func parse(_ html: String) -> [String: String]? {
        guard let open = html.range(of: "type=\"application/json\">"),
              let close = html.range(of: "</script>", range: open.upperBound..<html.endIndex)
        else { return nil }
        let json = String(html[open.upperBound..<close.lowerBound])
        // Undo the three ASCII escapes the blob applies, as `JSON.parse` would.
        let restored = json
            .replacingOccurrences(of: "\\u003c", with: "<")
            .replacingOccurrences(of: "\\u003e", with: ">")
            .replacingOccurrences(of: "\\u0026", with: "&")
        guard let data = restored.data(using: .utf8),
              let obj = try? JSONSerialization.jsonObject(with: data) as? [String: String]
        else { return nil }
        return obj
    }

    @Test("A value carrying </script> cannot close the block")
    func cannotBreakOut() {
        // The whole reason the three ASCII escapes are applied by hand: they are
        // ASCII, so JSON encoding alone passes them straight through. The root
        // CLAUDE.md records the same belief being false in the HTML export.
        let html = WelcomeIllustrationHTML.stringsBlock([
            "quote": "</script><img src=x onerror=alert(1)>"
        ])
        // Assert the PROPERTY, not the bytes. `JSONSerialization` turns out to
        // escape the forward slash as well (`<\\/script>`), so the literal
        // sequence is broken up twice over — but that is an undocumented detail
        // of the serialiser, and pinning it would make this test pass for a
        // reason we do not control. What must hold is that the only `</script>`
        // in the output is the two that close the blocks we wrote.
        let closers = html.components(separatedBy: "</script>").count - 1
        #expect(closers == 2, "a value closed the JSON block: \(closers) closers, expected 2")
        #expect(parse(html)?["quote"] == "</script><img src=x onerror=alert(1)>",
                "escaping must be reversible — the illustration still needs the words")
    }

    @Test("Ampersands and angle brackets survive as themselves")
    func entitiesRoundTrip() {
        // A participant saying "R&D" or "<3" is not an attack, and the words
        // have to reach the picture intact.
        let strings = ["a": "R&D said <3 of the flows", "b": "cost > benefit"]
        let parsed = parse(WelcomeIllustrationHTML.stringsBlock(strings))
        #expect(parsed == strings)
    }

    @Test("Quotes, newlines and non-ASCII survive — these are translations")
    func translationsRoundTrip() {
        // Curly quotes are in the shipped English already; the rest is what
        // twenty-one languages will bring.
        let strings = [
            "en": "\u{201C}where do I start?\u{201D}",
            "es": "\u{201C}\u{00BF}por d\u{00F3}nde empiezo?\u{201D}",
            "ja": "\u{300C}\u{3069}\u{3053}\u{304B}\u{3089}\u{59CB}\u{3081}\u{308C}\u{3070}\u{3044}\u{3044}\u{306E}\u{FF1F}\u{300D}",
            "ru": "\u{00AB}\u{0441} \u{0447}\u{0435}\u{0433}\u{043E} \u{043D}\u{0430}\u{0447}\u{0430}\u{0442}\u{044C}?\u{00BB}",
            "awkward": "line\nbreak \"quoted\" back\\slash",
        ]
        #expect(parse(WelcomeIllustrationHTML.stringsBlock(strings)) == strings)
    }

    @Test("The same table always produces the same bytes")
    func stable() {
        // Not tidiness: the webview reloads when its `.id` changes, and the HTML
        // is built fresh each time. Unsorted keys would make the markup differ
        // run to run for identical input.
        let strings = ["z": "last", "a": "first", "m": "middle", "b": "second"]
        let first = WelcomeIllustrationHTML.stringsBlock(strings)
        #expect(first == WelcomeIllustrationHTML.stringsBlock(strings))
        #expect(first.range(of: "\"a\"")!.lowerBound < first.range(of: "\"z\"")!.lowerBound)
    }

    @Test("An empty table degrades to no words, not to broken markup")
    func emptyIsSafe() {
        #expect(parse(WelcomeIllustrationHTML.stringsBlock([:])) == [:])
    }

    @Test("The themes illustration reads its words from the blob, not from literals")
    func themesUsesTheSeam() {
        let html = WelcomeIllustrationHTML.emergentThemes(
            dark: false, reduce: true,
            strings: ["a.name": "SENTINEL-A", "a.w0": "w0", "a.w1": "w1",
                      "a.w2": "w2", "a.w3": "w3", "b.name": "SENTINEL-B",
                      "b.w0": "x0", "b.w1": "x1", "b.w2": "x2", "b.w3": "x3"])
        #expect(html.contains("SENTINEL-A") && html.contains("SENTINEL-B"))
        // The English that used to be hardcoded in the JS must be gone from the
        // builder — otherwise the caller's table is decorative.
        #expect(!html.contains("How to begin unclear"))
        // And the fourth sink stays shut: no name is concatenated into markup.
        // Matches the *assignment*, not the bare word — the builder carries a
        // comment explaining why it uses textContent, and a test that forbids
        // naming the hazard forbids documenting it.
        #expect(!html.contains(".innerHTML="),
                "a string reaching innerHTML is outside the one escape site")
    }
}
