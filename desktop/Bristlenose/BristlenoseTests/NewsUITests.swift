import CryptoKit
import Foundation
import Testing

@testable import Bristlenose

// The decisions the news card, the first-run counts choice and the Settings
// rows make, as helpers (desktop/CLAUDE.md § Testing: a decision a view makes
// belongs in a testable helper). Pixels are not asserted here.

@Suite("News UI decisions")
@MainActor
struct NewsUITests {
    let suite = "news-ui-tests-\(UUID().uuidString)"
    let defaults: UserDefaults

    init() { defaults = UserDefaults(suiteName: suite)! }
    private func cleanUp() { defaults.removePersistentDomain(forName: suite) }

    // MARK: No key, no request (pure rule)

    @Test("A keyring with no usable key may not request; one real key may")
    func noKeysNoRequestRule() {
        let empty = NewsCheck.Keyring(base64Keys: ["k1": "", "k0": ""], backupKID: "k0")
        let malformed = NewsCheck.Keyring(base64Keys: ["k1": "not base64"], backupKID: nil)
        let real = NewsTestKit.keyring(["k1": .init()])
        #expect(!NewsCheck.mayRequest(with: empty))
        #expect(!NewsCheck.mayRequest(with: malformed))
        #expect(NewsCheck.mayRequest(with: real))
    }

    // MARK: First-run counts choice

    @Test("The counts choice starts off on a fresh install and is saved as an explicit answer")
    func countsChoiceDefaultsOffAndIsSaved() {
        defer { cleanUp() }
        let notManaged: (String) -> Bool = { _ in false }
        #expect(!NewsPreferences.countsChoiceStartsOn(in: defaults, isForced: notManaged))
        #expect(NewsPreferences.countsConsent(in: defaults, isForced: notManaged) == .unanswered)

        // Continue with the box unticked: an answer, and it is no.
        NewsPreferences.recordCountsAnswer(false, in: defaults, isForced: notManaged)
        #expect(defaults.object(forKey: NewsPreferences.countsKey) as? Bool == false)
        #expect(NewsPreferences.countsConsent(in: defaults, isForced: notManaged) == .no)

        // Ticked: yes, and a later showing starts ticked.
        NewsPreferences.recordCountsAnswer(true, in: defaults, isForced: notManaged)
        #expect(NewsPreferences.countsConsent(in: defaults, isForced: notManaged) == .yes)
        #expect(NewsPreferences.countsChoiceStartsOn(in: defaults, isForced: notManaged))
    }

    @Test("A managed counts key is never written, and the choice never starts on")
    func managedCountsAreNotWritten() {
        defer { cleanUp() }
        let managed: (String) -> Bool = { $0 == NewsPreferences.countsKey }
        NewsPreferences.recordCountsAnswer(true, in: defaults, isForced: managed)
        #expect(defaults.object(forKey: NewsPreferences.countsKey) == nil)
        defaults.set(true, forKey: NewsPreferences.countsKey)
        #expect(!NewsPreferences.countsChoiceStartsOn(in: defaults, isForced: managed))
    }

    // MARK: Settings rows

    @Test("Settings rows: news on by default, counts off until a yes, a profile locks either")
    func settingsRows() {
        defer { cleanUp() }
        let none: (String) -> Bool = { _ in false }
        #expect(NewsPreferences.newsRow(in: defaults, isForced: none) == .init(isOn: true, isLocked: false))
        #expect(NewsPreferences.countsRow(in: defaults, isForced: none) == .init(isOn: false, isLocked: false))
        defaults.set(true, forKey: NewsPreferences.countsKey)
        #expect(NewsPreferences.countsRow(in: defaults, isForced: none) == .init(isOn: true, isLocked: false))

        // Forced: locked, showing the value in force. A managed yes is not a yes.
        let forced: (String) -> Bool = { _ in true }
        defaults.set(false, forKey: NewsPreferences.enabledKey)
        #expect(NewsPreferences.newsRow(in: defaults, isForced: forced) == .init(isOn: false, isLocked: true))
        #expect(NewsPreferences.countsRow(in: defaults, isForced: forced) == .init(isOn: false, isLocked: true))
    }

    @Test("The Settings explanation carries one link, the privacy page, whatever the text says")
    func settingsExplanationLink() {
        let text = GeneralSettingsView.explanation("See [x](https://e.com) here.", privacy: "Privacy")
        let links = text.runs.compactMap(\.link)
        #expect(links == [NewsPreferences.privacyURL])
        #expect(String(text.characters) == "See [x](https://e.com) here. Privacy")
    }

    // MARK: The card

    @Test("A news item's words render literally; keyed slides keep the Markdown path")
    func remoteTextIsVerbatim() {
        let raw = "[x](https://e.com) and **bold**"
        #expect(WelcomeSlotProse.of(raw, remote: true) == .verbatim(raw))
        #expect(WelcomeSlotProse.of(raw, remote: false) == .markdown(raw))
    }

    @Test("The tag follows the slide: science on drawn slides, the tone's eyebrow on news")
    func toneToEyebrow() {
        #expect(WelcomeNewsTone.eyebrowKey(for: nil) == "desktop.welcome.home.tags.science")
        #expect(WelcomeNewsTone.eyebrowKey(for: .community) == "desktop.welcome.home.tags.community")
        #expect(WelcomeNewsTone.eyebrowKey(for: .news) == "desktop.welcome.home.tags.news")
        #expect(WelcomeNewsTone.tintAsset(for: .community, edo: false) == "PaletteDefaultCommunity")
        #expect(WelcomeNewsTone.tintAsset(for: .community, edo: true) == "PaletteEdoCommunity")
        #expect(WelcomeNewsTone.tintAsset(for: .news, edo: false) == "PaletteDefaultNews")
        #expect(WelcomeNewsTone.tintAsset(for: .news, edo: true) == "PaletteEdoNews")
    }

    @Test("Every eyebrow key and the rotator's spoken value exist in English")
    func eyebrowKeysResolve() throws {
        let i18n = I18n()
        i18n.configure(localesDirectory: try #require(I18n.findLocalesDirectory()))
        i18n.setLocale("en")
        #expect(i18n.t(WelcomeNewsTone.eyebrowKey(for: .community)) == "Community")
        #expect(i18n.t(WelcomeNewsTone.eyebrowKey(for: .news)) == "News")
        #expect(i18n.t("desktop.welcome.home.rotatorItem",
                       ["kind": "Community", "title": "Office hours", "n": "1", "total": "6"])
                == "Community, Office hours, 1 of 6")
    }

    // MARK: The rotator's place

    private func start(_ ids: [String], last: String = "", legacy: Int = -1, visits: Int = 3,
                       curriculum: Bool = false, lead: String? = nil) -> SlotRotation.Start {
        SlotRotation.start(ids: ids, lastID: last, legacyIndex: legacy, visits: visits,
                           curriculum: curriculum, leadID: lead, random: { _ in 0 })
    }

    @Test("A news item leads, and the reader's place is kept by id, not index")
    func rotatorPersistsByIDAndRemoteLeads() {
        let science = ["keyed:a", "keyed:b", "keyed:c"]
        // Next-per-visit by id.
        #expect(start(science, last: "keyed:b") == .init(index: 2, isLead: false))
        // A news item at the front leads, and says so (so the place is not overwritten).
        let withNews = ["news:office-hours"] + science
        #expect(start(withNews, last: "keyed:b", lead: "news:office-hours") == .init(index: 0, isLead: true))
        // The inserted item does not shift the place: one past b is still c.
        #expect(withNews[start(withNews, last: "keyed:b").index] == "keyed:c")
        // The item ended: its id is gone, and the card carries on from the start.
        #expect(start(science, last: "news:office-hours") == .init(index: 0, isLead: false))
        // A lead that is not in the list does nothing.
        #expect(start(science, last: "keyed:a", lead: "news:gone") == .init(index: 1, isLead: false))
    }

    @Test("Upgrade: with no id stored, the old index keeps the reader's place")
    func legacyIndexMigrates() {
        #expect(start(["keyed:a", "keyed:b", "keyed:c"], legacy: 0) == .init(index: 1, isLead: false))
        #expect(start(["keyed:a", "keyed:b", "keyed:c"], legacy: -1) == .init(index: 0, isLead: false))
    }

    @Test("Curriculum still tours in order, then never repeats the last slide")
    func curriculumUnchanged() {
        let tips = ["keyed:t1", "keyed:t2", "keyed:t3"]
        #expect(start(tips, visits: 1, curriculum: true).index == 1)
        // Tour done; random says 0, which was the last shown, so it moves on.
        #expect(start(tips, last: "keyed:t1", visits: 5, curriculum: true).index == 1)
    }
}
