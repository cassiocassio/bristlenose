import Foundation
import Testing

@testable import Bristlenose

/// Pins `DurationFormat.human` to the exact output of the Project dashboard's
/// `_format_duration_human` (`bristlenose/server/routes/dashboard.py`). The
/// window subtitle's total-session-time must read identically to the
/// dashboard's "Total" stat — if the Python formatter changes shape, this
/// test is the tripwire that says "mirror it here too."
@Suite struct DurationFormatTests {

    @Test func userExampleEighteenHoursTwentyThree() {
        // 18h 23m = 18*3600 + 23*60 = 66180 — the subtitle the spec quotes.
        #expect(DurationFormat.human(seconds: 66_180) == "18h 23m")
    }

    @Test func wholeHourDropsTheMinutes() {
        #expect(DurationFormat.human(seconds: 3_600) == "1h")
    }

    @Test func minutesOnlyBelowAnHour() {
        #expect(DurationFormat.human(seconds: 240) == "4m")
    }

    @Test func subMinuteIsLessThanOneM() {
        #expect(DurationFormat.human(seconds: 30) == "<1m")
        #expect(DurationFormat.human(seconds: 59) == "<1m")
    }

    @Test func exactlyOneMinute() {
        #expect(DurationFormat.human(seconds: 60) == "1m")
    }

    @Test func hoursAndMinutesTogether() {
        // 1h 1m 1s — seconds truncate, minute survives.
        #expect(DurationFormat.human(seconds: 3_661) == "1h 1m")
    }

    @Test func zeroAndNegativeBothZeroM() {
        #expect(DurationFormat.human(seconds: 0) == "0m")
        #expect(DurationFormat.human(seconds: -10) == "0m")
    }
}
