import AppKit
import Darwin
import Testing
@testable import Bristlenose

/// The report's right-click menus (docs/design-webview-context-menu.md §9.4).
/// WebKit builds the real menu in another process, so the edit is tested on
/// menus built here from WebKit's identifiers. Each row of §9.4 has a test.
@MainActor
@Suite("Report context menu")
struct ReportContextMenuTests {
    private final class Receiver: NSObject {
        @objc func pick(_ sender: Any?) {}
    }

    private typealias W = ReportContextMenu.WebKit

    /// Titles are the keys' last segment, so a test reads which string it got.
    private let t: (String) -> String = { String($0.split(separator: ".").last ?? "") }

    private func menu(_ ids: [NSUserInterfaceItemIdentifier?]) -> NSMenu {
        let m = NSMenu()
        for id in ids {
            guard let id else { m.addItem(.separator()); continue }
            let i = NSMenuItem(title: id.rawValue.replacingOccurrences(of: "WKMenuItemIdentifier", with: ""),
                               action: nil, keyEquivalent: "")
            i.identifier = id
            m.addItem(i)
        }
        return m
    }

    private var linkMenu: NSMenu {
        menu([W.openLink, W.openLinkInNewWindow, W.downloadLinkedFile, W.copyLink, nil, W.shareMenu])
    }
    private var imageMenu: NSMenu {
        menu([W.openImageInNewWindow, W.downloadImage, W.copyImage, W.copySubject, W.revealImage, nil, W.shareMenu])
    }
    private var pageMenu: NSMenu { menu([W.goBack, W.reload, nil]) }

    private func titles(_ m: NSMenu) -> [String] {
        m.items.map { $0.isSeparatorItem ? "—" : $0.title }
    }

    private func apply(_ m: NSMenu, _ target: ContextTarget?, editing: Bool = false) {
        ReportContextMenu.apply(to: m, target: target, isEditing: editing, t: t,
                                plural: { "\(t($0)):\($1)" },
                                receiver: Receiver(), action: #selector(Receiver.pick(_:)))
    }

    private static let media = ContextPlace.Media(key: "p2", seconds: 754.5)

    private func place(_ click: ContextPlace.Click, _ verb: ContextPlace.Verb = .show,
                       _ dest: ContextPlace.Dest = .transcript,
                       path: String = "/report/sessions/s3#t-754",
                       media: ContextPlace.Media? = media, anchor: String? = nil) -> ContextPlace {
        ContextPlace(click: click, verb: verb, dest: dest, path: path, media: media, anchor: anchor)
    }

    private func linkTarget(_ p: ContextPlace, here: Bool = false) -> ContextTarget {
        ContextTarget(seq: 1, place: p, here: here, link: .inReport)
    }

    private func commands(_ m: NSMenu) -> [ReportContextMenu.Command] {
        m.items.compactMap { ReportContextMenu.command(of: $0) }
    }

    // MARK: - §9.4, row by row

    @Test func aTimecodeThatPlaysLeadsWithPlay() {
        let m = linkMenu
        apply(m, linkTarget(place(.play)))
        #expect(titles(m) == ["play", "—", "revealInTranscript", "openTranscriptInNewWindow"])
        // D1: the new window plays too.
        #expect(commands(m)[2] == .newWindow(WindowPlace(path: "/report/sessions/s3#t-754",
                                                         anchor: nil, play: Self.media)))
        #expect(commands(m)[0] == .play(Self.media))
    }

    @Test func onItsOwnTranscriptATimecodeOffersNoShowInTranscript() {
        let m = linkMenu
        apply(m, linkTarget(place(.play), here: true))
        #expect(titles(m) == ["play", "—", "openTranscriptInNewWindow"])
    }

    @Test func aSpeakerBadgeShowsTheTranscriptAndOffersNoPlay() {
        let m = linkMenu
        apply(m, linkTarget(place(.navigate, media: nil)))
        #expect(titles(m) == ["revealInTranscript", "openTranscriptInNewWindow"])
        // A new window from a click that doesn't play doesn't play.
        #expect(commands(m)[1] == .newWindow(WindowPlace(path: "/report/sessions/s3#t-754",
                                                         anchor: nil, play: nil)))
    }

    @Test func aTimecodeThatShowsTheTranscriptOffersPlayLast() {
        let m = linkMenu
        apply(m, linkTarget(place(.navigate)))
        #expect(titles(m) == ["revealInTranscript", "openTranscriptInNewWindow", "—", "play"])
    }

    @Test func thresholdReviewsTimecodeLeadsWithTheNewWindowItsClickOpens() {
        let m = linkMenu
        apply(m, linkTarget(place(.window)))
        // Not Show in Transcript: it would navigate this window and close the review.
        #expect(titles(m) == ["openTranscriptInNewWindow", "—", "play"])
    }

    @Test func aSessionNumberOpensItsTranscript() {
        let m = linkMenu
        apply(m, linkTarget(place(.navigate, .open, path: "/report/sessions/s3",
                                  media: .init(key: "s3", seconds: 0))))
        #expect(titles(m) == ["openTranscript", "openTranscriptInNewWindow", "—", "play"])
    }

    @Test func aSessionFilenamePlaysFirst() {
        let m = linkMenu
        apply(m, linkTarget(place(.play, .open, path: "/report/sessions/s3",
                                  media: .init(key: "s3", seconds: 0))))
        #expect(titles(m) == ["play", "—", "openTranscript", "openTranscriptInNewWindow"])
    }

    /// A thumbnail is an image, not a link: its Copy Image, Copy Subject, Look Up
    /// and Share stay (D2), after ours.
    @Test func aSessionThumbnailKeepsTheImageItems() {
        let m = imageMenu
        apply(m, ContextTarget(seq: 1, place: place(.play, .open, path: "/report/sessions/s3",
                                                    media: .init(key: "s3", seconds: 0))))
        #expect(titles(m) == ["play", "—", "openTranscript", "openTranscriptInNewWindow", "—",
                              "CopyImage", "CopySubject", "RevealImage", "—", "ShareMenu"])
    }

    @Test func aHeadingElsewhereShowsItInQuotes() {
        let m = linkMenu
        apply(m, linkTarget(place(.navigate, .show, .quotes, path: "/report/quotes/#section-4", media: nil)))
        #expect(titles(m) == ["showInQuotes", "openQuotesInNewWindow"])
    }

    @Test func aStatCardNamingALensOpensIt() {
        let m = linkMenu
        apply(m, linkTarget(place(.navigate, .open, .lens, path: "/report/sessions/", media: nil)))
        #expect(titles(m) == ["open", "openInNewWindow"])
    }

    @Test func aContentsEntryGoesToItsSection() {
        let m = linkMenu
        apply(m, linkTarget(place(.navigate, .go, .quotes, path: "/report/quotes/#section-4",
                                  media: nil, anchor: "section-4")))
        #expect(titles(m) == ["goToSection", "openQuotesInNewWindow"])
        #expect(commands(m)[0] == .goTo(WindowPlace(path: "/report/quotes/#section-4",
                                                    anchor: "section-4", play: nil)))
    }

    @Test func aScreensVersionTimeWithNoSessionCanOnlyPlay() {
        let m = linkMenu
        apply(m, linkTarget(place(.play, path: "")))
        #expect(titles(m) == ["play"])
    }

    @Test func aScreengrabKeepsWebKitsImageItemsAndNoReload() {
        let m = imageMenu
        apply(m, ContextTarget(seq: 1, place: nil))
        #expect(titles(m) == ["CopyImage", "CopySubject", "RevealImage", "—", "ShareMenu"])
    }

    @Test func anOutsideLinkKeepsOpenCopyAndShare() {
        let m = linkMenu
        apply(m, ContextTarget(seq: 1, place: nil, link: .outside))
        #expect(titles(m) == ["OpenLink", "CopyLink", "—", "ShareMenu"])
    }

    /// An `href="#"` action (codebook rows, the hidden-quotes counter): its link
    /// items go, and the emptied menu falls back to Reload Report (D3).
    @Test func anInPageActionGetsReloadReportAlone() {
        let m = linkMenu
        apply(m, ContextTarget(seq: 1, place: nil, link: .inReport))
        #expect(titles(m) == ["reloadReport"])
    }

    @Test func thePageMenuGetsReloadReportInPlaceOfWebKitsReload() {
        let m = pageMenu
        apply(m, ContextTarget(seq: 1, place: nil))
        #expect(titles(m) == ["GoBack", "reloadReport"])
        #expect(m.items.last?.identifier == ReportContextMenu.reloadReport)
    }

    @Test func thePlayerVideoMenuLosesOpenDownloadAndCopyVideo() {
        let m = menu([W.openMediaInNewWindow, W.downloadMedia, W.copyMediaLink, nil,
                      W.id("ToggleFullScreen"), W.id("TogglePictureInPicture"), nil,
                      W.id("ShowHideMediaControls")])
        ReportContextMenu.applyToPlayer(m)
        #expect(titles(m) == ["ToggleFullScreen", "TogglePictureInPicture", "—", "ShowHideMediaControls"])
    }

    // MARK: - The quote card (D12)

    @Test func aQuoteCardOffersItsQuoteCommands() {
        let m = pageMenu
        let card = ContextCard(domId: "q-s3-754", starred: false, place: place(.navigate, media: nil))
        apply(m, ContextTarget(seq: 1, place: nil, card: card))
        #expect(titles(m) == ["star", "hide", "addTag", "—", "copyQuote", "—",
                              "revealInTranscript", "openTranscriptInNewWindow", "—",
                              "GoBack", "reloadReport"])
        #expect(commands(m)[3] == .copyQuote("q-s3-754"))
    }

    @Test func aStarredCardOffersUnstar() {
        let m = pageMenu
        apply(m, ContextTarget(seq: 1, place: nil,
                               card: ContextCard(domId: "q", starred: true, place: nil)))
        #expect(titles(m).first == "unstar")
    }

    /// Inside a mixed selection the right-clicked card may be starred while Star
    /// stars them all: the label follows what the action does, and counts.
    @Test func inASelectionTheCardMenuSaysWhatItDoesToAllOfThem() {
        let m = pageMenu
        apply(m, ContextTarget(seq: 1, place: nil,
                               card: ContextCard(domId: "q", starred: true, unstar: false, count: 3, place: nil)))
        #expect(titles(m).prefix(3) == ["starCount:3", "hide", "addTag"])
        #expect(titles(m).contains("copyQuotes"))
        let all = pageMenu
        apply(all, ContextTarget(seq: 1, place: nil,
                                 card: ContextCard(domId: "q", starred: true, unstar: true, count: 2, place: nil)))
        #expect(titles(all).first == "unstarCount:2")
    }

    /// A link inside a card (its timecode, its badge) gets the link's menu.
    @Test func aLinkInsideACardWinsOverTheCard() {
        let m = linkMenu
        apply(m, ContextTarget(seq: 1, place: place(.play), card: ContextCard(domId: "q", starred: false, place: nil),
                               link: .inReport))
        #expect(titles(m).first == "play")
        #expect(!titles(m).contains("star"))
    }

    // MARK: - Whatever the page said, or didn't

    /// The race lost, or a target this build can't read: the risky items go and
    /// nothing is added. The failure is a missing item, never the hijack.
    @Test func withNoTargetTheRiskyItemsGoAndNothingIsAdded() {
        let m = linkMenu
        apply(m, nil)
        #expect(titles(m) == ["OpenLink", "CopyLink", "—", "ShareMenu"])
        let img = imageMenu
        apply(img, nil)
        #expect(titles(img) == ["CopyImage", "CopySubject", "RevealImage", "—", "ShareMenu"])
    }

    @Test func withNoTargetThePageMenuStillReloads() {
        let m = pageMenu
        apply(m, nil)
        #expect(titles(m) == ["GoBack", "reloadReport"])
    }

    /// While a field has the keyboard nothing of ours is added and WebKit's own
    /// Reload goes too, since it would drop the typed words just the same.
    @Test func whileEditingNothingOfOursAndNoReload() {
        let m = menu([W.id("Cut"), W.reload])
        let card = ContextCard(domId: "q", starred: false, place: nil)
        apply(m, ContextTarget(seq: 1, place: nil, card: card), editing: true)
        #expect(titles(m) == ["Cut"])
        #expect(!ReportContextMenu.offersReload(isEditing: true))
    }

    @Test func aPlaceMenuGetsNoReload() {
        let m = menu([W.reload, nil, W.openLink, W.copyLink])
        apply(m, linkTarget(place(.navigate, media: nil)))
        #expect(!titles(m).contains("reloadReport"))
        #expect(!titles(m).contains("Reload"))
    }

    // MARK: - Freshness

    @Test func aTargetIsUsedByItsOwnMenuOnce() {
        let now = Date()
        var slot = ContextTargetSlot()
        slot.receive(ContextTarget(seq: 5, place: nil), at: now)
        #expect(slot.take(now: now)?.seq == 5)
        // Nothing new arrived: the next menu has no target.
        #expect(slot.take(now: now) == nil)
    }

    @Test func aTargetFromAnEarlierRightClickIsNotThisOnes() {
        let now = Date()
        var slot = ContextTargetSlot()
        slot.receive(ContextTarget(seq: 5, place: nil), at: now)
        _ = slot.take(now: now)
        slot.receive(ContextTarget(seq: 5, place: nil), at: now)
        #expect(slot.take(now: now) == nil)
        slot.receive(ContextTarget(seq: 6, place: nil), at: now.addingTimeInterval(-0.5))
        #expect(slot.take(now: now) == nil, "too old to be this right-click's")
    }

    /// The page numbers right-clicks from 1 in each document. After ⌘R, Reload
    /// Report or the reload when a run finishes, its first right-click must
    /// still be fresh (it read as already used until the count caught up).
    @Test func afterAReloadTheFirstRightClickIsFresh() {
        let now = Date()
        var slot = ContextTargetSlot()
        for seq in 1...40 {
            slot.receive(ContextTarget(seq: seq, place: nil), at: now)
            _ = slot.take(now: now)
        }
        slot.newDocument()
        slot.receive(ContextTarget(seq: 1, place: nil), at: now)
        #expect(slot.take(now: now)?.seq == 1)
    }

    /// A menu that silently lacks its items is undiagnosable; the slot says why.
    @Test func aRejectedTargetSaysWhy() {
        let now = Date()
        var slot = ContextTargetSlot()
        slot.receive(ContextTarget(seq: 3, place: nil), at: now.addingTimeInterval(-0.4))
        _ = slot.take(now: now)
        #expect(slot.lastRejection == .tooOld(ageMs: 400))
        slot.receive(ContextTarget(seq: 3, place: nil), at: now)
        _ = slot.take(now: now)
        #expect(slot.lastRejection == .alreadyUsed(seq: 3, lastSeq: 3))
        slot.receive(ContextTarget(seq: 4, place: nil), at: now)
        _ = slot.take(now: now)
        #expect(slot.lastRejection == nil)
    }

    @Test func anUnreadableMessageLeavesNoTarget() {
        let now = Date()
        var slot = ContextTargetSlot()
        slot.receive(ContextTarget(seq: 1, place: nil), at: now)
        slot.receiveUnreadable()
        #expect(slot.take(now: now) == nil)
    }

    // MARK: - WebKit's identifiers

    /// The identifiers are SPI: exported by WebKit, declared in no public header.
    /// Each constant we match on must equal its symbol's value, or an OS rename
    /// would quietly bring the default menu, hijack included, back.
    @Test func everyWebKitIdentifierWeMatchIsWebKitsOwn() throws {
        let pinned: [(NSUserInterfaceItemIdentifier, String)] = [
            (W.openLink, "OpenLink"), (W.openLinkInNewWindow, "OpenLinkInNewWindow"),
            (W.downloadLinkedFile, "DownloadLinkedFile"), (W.copyLink, "CopyLink"),
            (W.openImageInNewWindow, "OpenImageInNewWindow"), (W.downloadImage, "DownloadImage"),
            (W.copyImage, "CopyImage"), (W.copySubject, "CopySubject"), (W.revealImage, "RevealImage"),
            (W.openFrameInNewWindow, "OpenFrameInNewWindow"),
            (W.openMediaInNewWindow, "OpenMediaInNewWindow"), (W.downloadMedia, "DownloadMedia"),
            (W.copyMediaLink, "CopyMediaLink"), (W.shareMenu, "ShareMenu"),
            (W.reload, "Reload"), (W.goBack, "GoBack"),
        ]
        for (ours, name) in pinned {
            // The C name is `_WKMenuItemIdentifier…` (WebKit's SPI underscore); its
            // value is the identifier WebKit sets on the item.
            let symbol = "_WKMenuItemIdentifier" + name
            let raw = try #require(dlsym(WebKitHandle.handle, symbol), "WebKit no longer exports \(symbol)")
            let value = raw.assumingMemoryBound(to: NSString?.self).pointee as String?
            #expect(value == ours.rawValue, "\(symbol)")
        }
    }
}

/// WebKit, opened by path so the lookup doesn't depend on whether anything has
/// loaded it yet.
private enum WebKitHandle {
    static let handle = dlopen("/System/Library/Frameworks/WebKit.framework/WebKit", RTLD_NOW)
}
