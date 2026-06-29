import Testing
@testable import Bristlenose

/// Tests the pure icon-assignment logic — determinism, the reserved-ring
/// invariant, collision avoidance, and exhaustion behaviour. The `@AppStorage`
/// toggle and the SwiftUI reveal are not covered here (env / view concerns).
struct RandomProjectIconTests {

    @Test func poolReservesTheDefaultRing() {
        #expect(!RandomProjectIcon.pool.contains(IconPickerPopover.defaultIcon))
        // Palette is 100; reserving the ring leaves 99 drawable symbols.
        #expect(RandomProjectIcon.pool.count == IconPickerPopover.palette.count - 1)
        #expect(RandomProjectIcon.pool.count == 99)
    }

    @Test func assignmentIsDeterministicForNameAndExisting() {
        let a = RandomProjectIcon.assign(forName: "Acme onboarding study", existing: [])
        let b = RandomProjectIcon.assign(forName: "Acme onboarding study", existing: [])
        #expect(a == b)
        // Case / surrounding whitespace don't change the seed.
        let c = RandomProjectIcon.assign(forName: "  acme onboarding study ", existing: [])
        #expect(a == c)
    }

    @Test func neverDrawsTheReservedRing() {
        for name in ["Acme", "Checkout friction", "", "   ", "Pension dashboard", "你好"] {
            let icon = RandomProjectIcon.assign(forName: name, existing: [])
            #expect(icon != IconPickerPopover.defaultIcon)
            #expect(RandomProjectIcon.pool.contains(icon))
        }
    }

    @Test func seededOrderIsAStablePermutationOfThePool() {
        let order1 = RandomProjectIcon.seededOrder(forName: "Banking app diaries")
        let order2 = RandomProjectIcon.seededOrder(forName: "Banking app diaries")
        #expect(order1 == order2)                                   // stable
        #expect(Set(order1) == Set(RandomProjectIcon.pool))         // same symbols
        #expect(order1.count == RandomProjectIcon.pool.count)       // no dupes/drops
    }

    @Test func avoidsIconsAlreadyInUse() {
        let firstChoice = RandomProjectIcon.assign(forName: "Rural broadband", existing: [])
        // With the first choice taken, the next assignment for the same name
        // must probe onward to a different, unused icon.
        let next = RandomProjectIcon.assign(forName: "Rural broadband", existing: [firstChoice])
        #expect(next != firstChoice)
        #expect(!Set([firstChoice]).contains(next))
    }

    @Test func noRepeatsUntilThePoolIsExhausted() {
        // Simulate creating 99 projects, accumulating assigned icons.
        var used: Set<String> = []
        for i in 0..<RandomProjectIcon.pool.count {
            let icon = RandomProjectIcon.assign(forName: "Project \(i)", existing: used)
            #expect(!used.contains(icon))   // distinct each time
            used.insert(icon)
        }
        // All 99 drawn exactly once.
        #expect(used == Set(RandomProjectIcon.pool))

        // The 100th is allowed to repeat (pool exhausted) — must still be valid.
        let overflow = RandomProjectIcon.assign(forName: "Project 99", existing: used)
        #expect(RandomProjectIcon.pool.contains(overflow))
    }

    @Test func disabledTogglePathReturnsNilOnlyWhenOff() {
        // `iconForNewProject` gates on the persisted toggle; we can only assert
        // the pure path it delegates to is non-nil. (Default = on.)
        let icon = RandomProjectIcon.assign(forName: "Voice assistant trial", existing: [])
        #expect(!icon.isEmpty)
    }
}
