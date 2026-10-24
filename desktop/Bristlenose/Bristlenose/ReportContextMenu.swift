import AppKit

/// The report's right-click menu (docs/design-webview-context-menu.md §9.4).
///
/// WebKit builds the menu in its own process and hands it to
/// `BristlenoseWebView.willOpenMenu`; this edits it. What the click landed on
/// comes from the page (`ContextTarget`), posted just before. The first item is
/// what a single click on the thing does; then the same over there (a new
/// window); then the other useful thing (Play, or the transcript).
///
/// Three rules hold whatever the page said, or failed to say:
/// - WebKit's new-window and download items never stay. "Open Link in New
///   Window" put a report page in the player's window, and the downloads did
///   nothing. Nothing replaces them unless the target is known.
/// - A link into the report loses Open Link, Copy Link and Share: its address is
///   a loopback URL that dies with the serve.
/// - Reload Report takes the place of WebKit's Reload on page and text menus,
///   never on a link, image or place menu (Safari's rule, D6), and never while a
///   field has the keyboard, where it would drop the typed words.
///
/// Pure, so the edit is tested on menus built here.
enum ReportContextMenu {
    /// WebKit's item identifiers. SPI: the SDK exports the symbols but no header
    /// declares them, so `ReportContextMenuTests` pins each literal against the
    /// symbol's value. An OS rename then fails a test instead of quietly
    /// bringing back the default menu.
    enum WebKit {
        static let openLink = id("OpenLink")
        static let openLinkInNewWindow = id("OpenLinkInNewWindow")
        static let downloadLinkedFile = id("DownloadLinkedFile")
        static let copyLink = id("CopyLink")
        static let openImageInNewWindow = id("OpenImageInNewWindow")
        static let downloadImage = id("DownloadImage")
        static let copyImage = id("CopyImage")
        static let copySubject = id("CopySubject")
        static let revealImage = id("RevealImage")
        static let openFrameInNewWindow = id("OpenFrameInNewWindow")
        static let openMediaInNewWindow = id("OpenMediaInNewWindow")
        static let downloadMedia = id("DownloadMedia")
        static let copyMediaLink = id("CopyMediaLink")
        static let shareMenu = id("ShareMenu")
        static let reload = id("Reload")
        static let goBack = id("GoBack")

        static func id(_ name: String) -> NSUserInterfaceItemIdentifier {
            NSUserInterfaceItemIdentifier("WKMenuItemIdentifier" + name)
        }

        /// Never kept: the routes that opened a report page in the player's
        /// window, and the downloads that did nothing.
        static let neverKept: Set<NSUserInterfaceItemIdentifier> = [
            openLinkInNewWindow, downloadLinkedFile, openImageInNewWindow, downloadImage,
            openFrameInNewWindow, openMediaInNewWindow, downloadMedia,
        ]

        /// A link's own items: what makes a menu a link menu.
        static let linkItems: Set<NSUserInterfaceItemIdentifier> = [openLink, copyLink]
        /// An image's own items: what makes a menu an image menu.
        static let imageItems: Set<NSUserInterfaceItemIdentifier> = [copyImage, copySubject, revealImage]
    }

    /// Kept for the sibling that wraps the player's video menu.
    static let webKitReload = WebKit.reload
    static let reloadReport = NSUserInterfaceItemIdentifier("app.bristlenose.reloadReport")

    /// What one of our items does when chosen.
    enum Command: Equatable {
        case play(ContextPlace.Media)
        case goTo(WindowPlace)
        case newWindow(WindowPlace)
        case star, hide, addTag
        case copyQuote(String)
        case reload
    }

    /// Carries a `Command` on `NSMenuItem.representedObject`.
    final class CommandBox: NSObject {
        let command: Command
        init(_ command: Command) { self.command = command }
    }

    /// The chosen item's command.
    static func command(of item: Any?) -> Command? {
        ((item as? NSMenuItem)?.representedObject as? CommandBox)?.command
    }

    /// Not while a field has the keyboard (`isEditing`: any focused input,
    /// textarea or editable text, the search box included): what is typed there
    /// is saved only when the edit is committed, and a reload would drop it. A
    /// deliberate over-approximation; clicking out of the field brings it back.
    static func offersReload(isEditing: Bool) -> Bool { !isEditing }

    // MARK: - The edit

    /// - Parameters:
    ///   - target: what the page said the right-click landed on, or nil when it
    ///     said nothing this build can read in time (`BristlenoseWebView`
    ///     decides freshness).
    ///   - t: the string table, `I18n.t`; `plural`, `I18n.plural`.
    static func apply(
        to menu: NSMenu, target: ContextTarget?, isEditing: Bool,
        t: (String) -> String, plural: (String, Int) -> String = { key, _ in key },
        receiver: AnyObject, action: Selector
    ) {
        removeNeverKept(from: menu)
        if target?.link == .inReport {
            let image = menu.items.contains { $0.identifier.map(WebKit.imageItems.contains) == true }
            for item in menu.items {
                guard let id = item.identifier else { continue }
                if WebKit.linkItems.contains(id) || (!image && id == WebKit.shareMenu) {
                    menu.removeItem(item)
                }
            }
        }

        let ours = isEditing ? [] : groups(for: target, t: t, plural: plural)
        let place = target?.place != nil

        // Reload Report: in WebKit's Reload's place on a page or text menu,
        // appended to one that has been emptied (an `href="#"` action's link
        // menu, D3), and nowhere else.
        let reloadAt = menu.items.firstIndex { $0.identifier == WebKit.reload }
        if let reloadAt { menu.removeItem(at: reloadAt) }
        if offersReload(isEditing: isEditing), !place {
            let item = makeItem(t("desktop.menu.view.reloadReport"), .reload, receiver, action)
            item.identifier = reloadReport
            let content = menu.items.contains {
                $0.identifier.map { WebKit.linkItems.contains($0) || WebKit.imageItems.contains($0) } == true
            }
            if let reloadAt {
                menu.insertItem(item, at: min(reloadAt, menu.items.count))
            } else if ours.isEmpty, !content {
                menu.addItem(.separator())
                menu.addItem(item)
            }
        }

        // Ours first, then WebKit's remainder.
        var at = 0
        for (i, group) in ours.enumerated() {
            if i > 0 {
                menu.insertItem(.separator(), at: at)
                at += 1
            }
            for (title, command) in group {
                menu.insertItem(makeItem(title, command, receiver, action), at: at)
                at += 1
            }
        }
        if !ours.isEmpty { menu.insertItem(.separator(), at: at) }
        tidySeparators(menu)
    }

    /// WebKit's new-window and download items, gone whatever else happens.
    static func removeNeverKept(from menu: NSMenu) {
        for item in menu.items where item.identifier.map(WebKit.neverKept.contains) == true {
            menu.removeItem(item)
        }
        tidySeparators(menu)
    }

    /// The player window's video menu (D8): WebKit's own Play, Mute, Full
    /// Screen, Picture in Picture and controls items, without Open, Download and
    /// Copy Video. Those open a loopback media URL in the player's window, save
    /// nothing, and copy an address that dies with the serve.
    static func applyToPlayer(_ menu: NSMenu) {
        let gone = WebKit.neverKept.union([WebKit.copyMediaLink])
        for item in menu.items where item.identifier.map(gone.contains) == true {
            menu.removeItem(item)
        }
        tidySeparators(menu)
    }

    // MARK: - Our items

    typealias Group = [(String, Command)]

    static func groups(
        for target: ContextTarget?, t: (String) -> String,
        plural: (String, Int) -> String = { key, _ in key }
    ) -> [Group] {
        guard let target else { return [] }
        if let place = target.place { return placeGroups(place, here: target.here, t: t) }
        if let card = target.card { return cardGroups(card, t: t, plural: plural) }
        return []
    }

    /// §9.4, one row per target: the click first, then the same in a new
    /// window, then the other thing.
    static func placeGroups(_ place: ContextPlace, here: Bool, t: (String) -> String) -> [Group] {
        // A link whose click plays, with nothing to play, is a link to its page.
        let click: ContextPlace.Click = place.click == .play && place.media == nil ? .navigate : place.click
        let goes = !place.path.isEmpty
        let nav: (String, Command)? = goes && !(place.dest == .transcript && here)
            ? (navTitle(place, t), .goTo(WindowPlace(path: place.path, anchor: place.anchor, play: nil)))
            : nil
        // D1: from a target whose click plays, the new window plays too.
        let newWindow: (String, Command)? = goes
            ? (newWindowTitle(place.dest, t), .newWindow(WindowPlace(place: place, play: click == .play)))
            : nil
        let play: (String, Command)? = place.media.map { (t("desktop.menu.video.play"), .play($0)) }

        let groups: [Group]
        switch click {
        case .play: groups = [[play].compactMap { $0 }, [nav, newWindow].compactMap { $0 }]
        case .navigate: groups = [[nav, newWindow].compactMap { $0 }, [play].compactMap { $0 }]
        // The click opens a new window so the dialog it sits in stays open (threshold
        // review); going there in this window would close it, so that is not offered.
        case .window: groups = [[newWindow].compactMap { $0 }, [play].compactMap { $0 }]
        }
        return groups.filter { !$0.isEmpty }
    }

    /// The quote card's own menu (D12): the Quotes menu's commands for this card,
    /// or for the selection it sits in, labelled as the Quotes menu labels them
    /// ("Star 3 Quotes"), so the item says what choosing it does.
    static func cardGroups(
        _ card: ContextCard, t: (String) -> String,
        plural: (String, Int) -> String = { key, _ in key }
    ) -> [Group] {
        let base = card.unstar ? "unstar" : "star"
        let star = card.count > 0
            ? plural("desktop.menu.quotes.\(base)Count", card.count)
            : t("desktop.menu.quotes.\(base)")
        let copy = t(card.count > 1 ? "desktop.menu.quotes.copyQuotes" : "desktop.menu.context.copyQuote")
        var groups: [Group] = [
            [
                (star, .star),
                (t("desktop.menu.quotes.hide"), .hide),
                (t("desktop.menu.quotes.addTag"), .addTag),
            ],
            [(copy, .copyQuote(card.domId))],
        ]
        if let place = card.place, !place.path.isEmpty {
            groups.append([
                (t("desktop.menu.quotes.revealInTranscript"),
                 .goTo(WindowPlace(path: place.path, anchor: nil, play: nil))),
                (t("desktop.menu.context.openTranscriptInNewWindow"),
                 .newWindow(WindowPlace(place: place, play: false))),
            ])
        }
        return groups
    }

    static func navTitle(_ place: ContextPlace, _ t: (String) -> String) -> String {
        switch (place.verb, place.dest) {
        case (.go, _): return t("desktop.menu.context.goToSection")
        case (.show, .quotes): return t("desktop.menu.context.showInQuotes")
        case (.show, _): return t("desktop.menu.quotes.revealInTranscript")
        case (.open, .transcript): return t("desktop.menu.context.openTranscript")
        case (.open, .quotes), (.open, .lens): return t("desktop.menu.context.open")
        }
    }

    static func newWindowTitle(_ dest: ContextPlace.Dest, _ t: (String) -> String) -> String {
        switch dest {
        case .transcript: return t("desktop.menu.context.openTranscriptInNewWindow")
        case .quotes: return t("desktop.menu.context.openQuotesInNewWindow")
        case .lens: return t("desktop.menu.file.openInNewWindow")
        }
    }

    // MARK: - Helpers

    static func makeItem(_ title: String, _ command: Command, _ receiver: AnyObject, _ action: Selector) -> NSMenuItem {
        let item = NSMenuItem(title: title, action: action, keyEquivalent: "")
        item.target = receiver
        item.representedObject = CommandBox(command)
        return item
    }

    /// No separator first, last, or twice in a row.
    static func tidySeparators(_ menu: NSMenu) {
        var previousWasSeparator = true
        for item in menu.items {
            if item.isSeparatorItem {
                if previousWasSeparator { menu.removeItem(item) } else { previousWasSeparator = true }
            } else {
                previousWasSeparator = false
            }
        }
        while let last = menu.items.last, last.isSeparatorItem { menu.removeItem(last) }
    }
}
