import Foundation
import Testing

@testable import Bristlenose

// The transcript file the import writes, held to the golden fixtures byte for
// byte — the same three files `tests/test_parse_subtitles.py` parses on the
// Python side. One writer, one reader, one set of bytes between them.
//
// If a golden comparison fails, diff the rendered string
// against the fixture before touching either: the fixture is what pytest
// already accepts, so it is the writer that moves.

@Suite("Platform transcript writer")
struct PlatformTranscriptWriterTests {

    nonisolated private static let fixtures = URL(fileURLWithPath: #filePath)
        .deletingLastPathComponent()   // BristlenoseTests
        .deletingLastPathComponent()   // Bristlenose
        .deletingLastPathComponent()   // desktop
        .deletingLastPathComponent()   // repo root
        .appendingPathComponent("tests/fixtures/platform-transcripts")

    private func golden(_ name: String) throws -> Data {
        try Data(contentsOf: Self.fixtures.appendingPathComponent(name))
    }

    /// Meet, named, Portuguese, with the two characters WebVTT reserves inside
    /// the spoken text — `Ponte & Filhos`, `<Pagamentos>` — so the escape is
    /// exercised by the same bytes the reader unescapes.
    @Test("A named Meet transcript renders the golden bytes")
    func namedGolden() throws {
        let cues = [
            PlatformTranscriptCue(start: 0, end: 3.25, speaker: "Ana Souza",
                                  text: "Olá, tudo bem? Vamos começar."),
            PlatformTranscriptCue(start: 3.9, end: 9.12, speaker: "Bruno Lima",
                                  text: "Tudo bem, sim. Eu uso o aplicativo da Ponte & Filhos todo dia."),
            PlatformTranscriptCue(start: 9.8, end: 14.0, speaker: "Ana Souza",
                                  text: "E o que acontece quando você abre a tela <Pagamentos>?"),
            PlatformTranscriptCue(start: 14.4, end: 21.0, speaker: "Bruno Lima",
                                  text: "Honestamente: nada. Fica carregando e eu desisto."),
            PlatformTranscriptCue(start: 21.5, end: 24.0, speaker: "Ana Souza",
                                  text: "Entendi. Pode me mostrar?"),
        ]
        let note = PlatformTranscriptNote(
            source: .meet, language: "pt-BR",
            media: "2026-09-24 0934 — P07 Interview.mp4",
            mediaDuration: 3131.42, rebasedBy: 0, droppedOutsideMedia: 0)
        let rendered = PlatformTranscriptWriter.render(cues: cues, note: note)
        #expect(Data(rendered.utf8) == (try golden("cloud-transcript-named.vtt")))
    }

    /// Teams, nobody named: no `<v>` anywhere and `speakers: none`, derived
    /// from the cues rather than stated. The text keeps its `Note:` and
    /// `Honestly:` openers — the writer leaves a colon alone, and the reader's
    /// name heuristic is off for cloud files.
    @Test("An unnamed Teams transcript renders the golden bytes")
    func unnamedGolden() throws {
        let cues = [
            PlatformTranscriptCue(start: 0, end: 2.8, text: "Right, shall we start with the kiosk?"),
            PlatformTranscriptCue(start: 3.1, end: 8.4,
                                  text: "Note: the prototype crashed on me twice yesterday, so bear with it."),
            PlatformTranscriptCue(start: 8.9, end: 12.0,
                                  text: "Honestly: I never found the basket button at all."),
            PlatformTranscriptCue(start: 12.3, end: 15.0,
                                  text: "Okay. Talk me through what you were expecting."),
        ]
        let note = PlatformTranscriptNote(
            source: .teams, language: "en-GB",
            media: "2026-09-18 1400 — Kiosk round 2.mp4",
            mediaDuration: 1806, rebasedBy: 0, droppedOutsideMedia: 0)
        let rendered = PlatformTranscriptWriter.render(cues: cues, note: note)
        #expect(Data(rendered.utf8) == (try golden("cloud-transcript-unnamed.vtt")))
    }

    /// The rebase case, end to end: vendor cues on the call's clock, a recording
    /// that began 12.4 s in, three cues before the button, and a last cue that
    /// runs 1.1 s past the file and is clamped rather than refused.
    @Test("A rebased Zoom transcript with drops renders the golden bytes")
    func rebasedGolden() throws {
        let callClock = [
            PlatformTranscriptCue(start: 0.0, end: 3.0, speaker: "Jürgen Müller", text: "Hallo?"),
            PlatformTranscriptCue(start: 3.5, end: 8.0, speaker: "Işık Barış", text: "Hallo, ja."),
            PlatformTranscriptCue(start: 8.5, end: 12.0, speaker: "Jürgen Müller", text: "Einen Moment."),
            PlatformTranscriptCue(start: 12.4, end: 14.0, speaker: "Jürgen Müller",
                                  text: "Also, dann fangen wir an."),
            PlatformTranscriptCue(start: 14.4, end: 19.3, speaker: "Işık Barış",
                                  text: "Gern: ich habe die App letzte Woche installiert."),
            PlatformTranscriptCue(start: 19.7, end: 23.4, speaker: "Jürgen Müller",
                                  text: "Und wie war der erste Eindruck?"),
            PlatformTranscriptCue(start: 2420.4, end: 2424.0, speaker: "Işık Barış",
                                  text: "Ehrlich gesagt ziemlich verwirrend."),
        ]
        let shift: TimeInterval = -12.4
        let duration: TimeInterval = 2410.5
        #expect(!PlatformTranscriptRebase.tailRunsPast(callClock, by: shift, mediaDuration: duration),
                "1.1 s past the end is the platform's imprecision, not the wrong recording")
        let rebased = PlatformTranscriptRebase.rebase(callClock, by: shift, mediaDuration: duration)
        #expect(rebased.dropped == 3)
        #expect(rebased.cues.count == 4)
        #expect(rebased.cues.first?.start == 0)
        #expect(rebased.cues.last?.end == duration, "the tail is clamped to the file's end")

        let note = PlatformTranscriptNote(
            source: .zoom, language: "de",
            media: "2026-09-30 1100 — Onboarding Interview 3.mp4",
            mediaDuration: duration, rebasedBy: shift, droppedOutsideMedia: rebased.dropped)
        let rendered = PlatformTranscriptWriter.render(cues: rebased.cues, note: note)
        #expect(Data(rendered.utf8) == (try golden("cloud-transcript-rebased-drops.vtt")))
    }

    @Test("Timestamps are HH:MM:SS.mmm with two-digit hours")
    func timestamps() {
        #expect(PlatformTranscriptWriter.timestamp(0) == "00:00:00.000")
        #expect(PlatformTranscriptWriter.timestamp(2408) == "00:40:08.000")
        #expect(PlatformTranscriptWriter.timestamp(3661.5) == "01:01:01.500")
        // Rounded to the millisecond once, not truncated: 1.5999999999999996
        // is 1.600, which is what the fixture carries.
        #expect(PlatformTranscriptWriter.timestamp(14.0 - 12.4) == "00:00:01.600")
        #expect(PlatformTranscriptWriter.timestamp(-1) == "00:00:00.000", "never negative")
    }

    @Test("Durations carry three decimals, a trailing s, and a sign")
    func durations() {
        #expect(PlatformTranscriptWriter.seconds(3131.42) == "3131.420s")
        #expect(PlatformTranscriptWriter.seconds(0) == "0.000s")
        #expect(PlatformTranscriptWriter.seconds(-12.4) == "-12.400s")
        #expect(PlatformTranscriptWriter.seconds(1806) == "1806.000s")
    }

    /// The reader unescapes exactly these three, so a name or a line carrying
    /// them round-trips; anything that would break the framing is removed.
    @Test("Reserved characters are escaped and framing breakers removed")
    func escaping() {
        #expect(PlatformTranscriptWriter.escape("Ponte & Filhos") == "Ponte &amp; Filhos")
        #expect(PlatformTranscriptWriter.escape("<Pagamentos>") == "&lt;Pagamentos&gt;")
        #expect(PlatformTranscriptWriter.escape("one\ntwo\r\nthree") == "one two three")
        #expect(!PlatformTranscriptWriter.escape("a --> b").contains("-->"))
        #expect(!PlatformTranscriptWriter.escape("a --> b").contains("--&gt;"))
    }

    @Test("A name with a reserved character is escaped inside the voice tag")
    func nameEscaping() {
        let cue = PlatformTranscriptCue(start: 0, end: 1, speaker: "R&D <Guest>", text: "Hi.")
        let note = PlatformTranscriptNote(source: .meet, language: nil, media: "m.mp4",
                                          mediaDuration: 10, rebasedBy: 0, droppedOutsideMedia: 0)
        let rendered = PlatformTranscriptWriter.render(cues: [cue], note: note)
        #expect(rendered.contains("<v R&amp;D &lt;Guest&gt;>Hi.</v>"))
        // No language said → no `language:` line, rather than an empty one the
        // reader would take as a tag.
        #expect(!rendered.contains("language:"))
    }

    @Test("A cue with nothing said is not written, and does not make the file named")
    func blankCuesAreSkipped() {
        let cues = [
            PlatformTranscriptCue(start: 0, end: 1, speaker: "Someone", text: "   "),
            PlatformTranscriptCue(start: 1, end: 2, text: "Said."),
        ]
        let note = PlatformTranscriptNote(source: .meet, language: nil, media: "m.mp4",
                                          mediaDuration: 10, rebasedBy: 0, droppedOutsideMedia: 0)
        let rendered = PlatformTranscriptWriter.render(cues: cues, note: note)
        #expect(rendered.contains("speakers: none"))
        #expect(!rendered.contains("<v "))
        #expect(rendered.hasSuffix("Said.\n"))
    }

    @Test("A NOTE value is kept on one line")
    func noteValuesStayOnOneLine() {
        #expect(PlatformTranscriptWriter.noteValue("two\nlines") == "two lines")
    }
}

@Suite("Platform transcript rebase")
struct PlatformTranscriptRebaseTests {

    private func cue(_ start: TimeInterval, _ end: TimeInterval) -> PlatformTranscriptCue {
        PlatformTranscriptCue(start: start, end: end, text: "…")
    }

    @Test("A cue straddling the record button is clamped to zero, never negative")
    func straddlingStartClamps() {
        let out = PlatformTranscriptRebase.rebase([cue(10, 15)], by: -12, mediaDuration: 100)
        #expect(out.dropped == 0)
        #expect(out.cues == [PlatformTranscriptCue(start: 0, end: 3, text: "…")])
    }

    @Test("A cue wholly before the record button is dropped and counted")
    func whollyBeforeDrops() {
        let out = PlatformTranscriptRebase.rebase([cue(0, 5), cue(20, 25)], by: -12, mediaDuration: 100)
        #expect(out.dropped == 1)
        #expect(out.cues.map(\.start) == [8])
    }

    @Test("A cue wholly after the file ends is dropped; one that straddles the end is clamped")
    func pastTheEnd() {
        let out = PlatformTranscriptRebase.rebase([cue(99, 101), cue(100, 104)], by: 0, mediaDuration: 100)
        #expect(out.dropped == 1)
        #expect(out.cues == [PlatformTranscriptCue(start: 99, end: 100, text: "…")])
    }

    @Test("A cue that ends exactly at zero is wholly before the media")
    func endsAtZero() {
        let out = PlatformTranscriptRebase.rebase([cue(0, 12)], by: -12, mediaDuration: 100)
        #expect(out.dropped == 1)
        #expect(out.cues.isEmpty)
    }

    @Test("The tail check looks before clamping, in the direction the first draft missed")
    func tailCheck() {
        let cues = [cue(0, 10), cue(90, 102.5)]
        #expect(PlatformTranscriptRebase.tailRunsPast(cues, by: 0, mediaDuration: 100))
        #expect(!PlatformTranscriptRebase.tailRunsPast(cues, by: 0, mediaDuration: 101))
        #expect(!PlatformTranscriptRebase.tailRunsPast([cue(0, 101.9)], by: 0, mediaDuration: 100),
                "inside the two-second tolerance")
        #expect(PlatformTranscriptRebase.tailRunsPast([cue(0, 10)], by: 95, mediaDuration: 100),
                "the shift is part of the measurement")
        #expect(!PlatformTranscriptRebase.tailRunsPast([], by: 0, mediaDuration: 100))
    }

    @Test("Order and speakers survive the rebase")
    func orderAndSpeakersSurvive() {
        let cues = [
            PlatformTranscriptCue(start: 5, end: 6, speaker: "A", text: "one"),
            PlatformTranscriptCue(start: 7, end: 8, speaker: "B", text: "two"),
        ]
        let out = PlatformTranscriptRebase.rebase(cues, by: -5, mediaDuration: 100)
        #expect(out.cues.map(\.speaker) == ["A", "B"])
        #expect(out.cues.map(\.text) == ["one", "two"])
    }
}
