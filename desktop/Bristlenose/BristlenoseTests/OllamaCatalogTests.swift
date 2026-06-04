import Testing
@testable import Bristlenose

/// Pure-function coverage for the on-device model catalogue. These encode
/// behavioural contracts a user would notice — the RAM→model recommendation,
/// which rows are selectable, and when the low-disk advisory fires — and pin
/// the deliberate, easy-to-regress boundaries (notably `>= 15`, not 16).
///
/// All functions under test are env-free pure cores, so they're deterministic
/// regardless of the run scheme's `BRISTLENOSE_DEBUG_OLLAMA_TAG` override.
@Suite("Ollama catalog")
struct OllamaCatalogTests {

    // MARK: - recommendedTag waterfall (tagForRAM core)

    @Test func tagForRAM_topTier_47AndAbove() {
        #expect(OllamaCatalog.tagForRAM(47) == "gemma4:31b")
        #expect(OllamaCatalog.tagForRAM(64) == "gemma4:31b")
        #expect(OllamaCatalog.tagForRAM(128) == "gemma4:31b")
    }

    @Test func tagForRAM_justBelow47_dropsTo26b() {
        #expect(OllamaCatalog.tagForRAM(46.9) == "gemma4:26b")
    }

    @Test func tagForRAM_midTier_35to47() {
        #expect(OllamaCatalog.tagForRAM(35) == "gemma4:26b")
        #expect(OllamaCatalog.tagForRAM(36) == "gemma4:26b")
    }

    @Test func tagForRAM_justBelow35_dropsToE4b() {
        #expect(OllamaCatalog.tagForRAM(34.9) == "gemma4:e4b")
    }

    /// The load-bearing boundary: a "16 GB" Mac whose `physicalMemory` reports
    /// ~15.x must still get e4b, not the llama floor. `>= 15`, never 16.
    @Test func tagForRAM_fifteenIsTheFloorForE4b() {
        #expect(OllamaCatalog.tagForRAM(15) == "gemma4:e4b")
        #expect(OllamaCatalog.tagForRAM(15.5) == "gemma4:e4b")  // typical "16 GB" Mac
        #expect(OllamaCatalog.tagForRAM(32) == "gemma4:e4b")    // 32 < 35 → still e4b
    }

    @Test func tagForRAM_justBelow15_fallsToLlama() {
        #expect(OllamaCatalog.tagForRAM(14.9) == "llama3.2:3b")
    }

    @Test func tagForRAM_lowRAM_floorsAtLlama() {
        #expect(OllamaCatalog.tagForRAM(4) == "llama3.2:3b")
        #expect(OllamaCatalog.tagForRAM(8) == "llama3.2:3b")
        #expect(OllamaCatalog.tagForRAM(0) == "llama3.2:3b")
    }

    // MARK: - fits (selectable rows)

    @Test func fits_atExactFloor_isTrue() {
        for m in OllamaCatalog.curated {
            #expect(OllamaCatalog.fits(m, ramGB: m.minRAMGB),
                    "\(m.tag) should fit at exactly its minRAMGB")
        }
    }

    @Test func fits_justBelowFloor_isFalse() {
        for m in OllamaCatalog.curated {
            #expect(!OllamaCatalog.fits(m, ramGB: m.minRAMGB - 0.1),
                    "\(m.tag) should NOT fit just below its minRAMGB")
        }
    }

    // MARK: - largestSelectable (drives the low-disk advisory target)

    @Test func largestSelectable_picksBiggestWeightsThatFits() {
        #expect(OllamaCatalog.largestSelectable(forRAMGB: 4)?.tag == "llama3.2:3b")
        #expect(OllamaCatalog.largestSelectable(forRAMGB: 8)?.tag == "gemma4:e4b")
        #expect(OllamaCatalog.largestSelectable(forRAMGB: 24)?.tag == "gemma4:26b")
        #expect(OllamaCatalog.largestSelectable(forRAMGB: 32)?.tag == "gemma4:31b")
        #expect(OllamaCatalog.largestSelectable(forRAMGB: 64)?.tag == "gemma4:31b")
    }

    @Test func largestSelectable_noModelFits_isNil() {
        #expect(OllamaCatalog.largestSelectable(forRAMGB: 2) == nil)
    }

    // MARK: - isLowDisk (advisory only)

    @Test func isLowDisk_freeBelowLargest_warns() {
        // 32 GB Mac → largest selectable is 31b (20 GB weights). 19 GB free → warn.
        #expect(OllamaCatalog.isLowDisk(freeBytes: 19_000_000_000, ramGB: 32))
    }

    @Test func isLowDisk_freeAboveLargest_doesNotWarn() {
        // 21 GB free clears the 20 GB threshold.
        #expect(!OllamaCatalog.isLowDisk(freeBytes: 21_000_000_000, ramGB: 32))
    }

    @Test func isLowDisk_smallerMacUsesSmallerThreshold() {
        // 8 GB Mac → largest selectable is e4b (3 GB weights). 2 GB free → warn,
        // 4 GB free → fine. Confirms the threshold tracks the *selectable* model,
        // not a fixed figure.
        #expect(OllamaCatalog.isLowDisk(freeBytes: 2_000_000_000, ramGB: 8))
        #expect(!OllamaCatalog.isLowDisk(freeBytes: 4_000_000_000, ramGB: 8))
    }

    @Test func isLowDisk_unknownFreeSpace_doesNotCryWolf() {
        #expect(!OllamaCatalog.isLowDisk(freeBytes: nil, ramGB: 32))
    }

    @Test func isLowDisk_noSelectableModel_doesNotWarn() {
        #expect(!OllamaCatalog.isLowDisk(freeBytes: 0, ramGB: 2))
    }
}
