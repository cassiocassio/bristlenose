import AppKit
import SwiftUI

/// macOS 26+, AppKit outline sidebar only: puts `SidebarFooter` in a
/// bottom-aligned **split view item accessory**, so the project list slides
/// under it behind the system's soft scroll edge — the same effect the list gets
/// under the toolbar at the top. `docs/design-desktop-sidebar-footer.md`.
///
/// **Why an accessory and not `.safeAreaBar`.** `safeAreaBar` gives the soft
/// edge to SwiftUI scroll views only. The outline is an `NSScrollView` hosted in
/// SwiftUI, so under `safeAreaBar` it stopped dead at the footer (measured,
/// 3 Oct 2026). AppKit draws its scroll edge effect where a scroll view meets
/// the chrome above or below it: the toolbar, a titlebar accessory, or a split
/// view item accessory. `NSScrollView` itself has no edge-effect property.
///
/// **Why a probe.** `NavigationSplitView` owns the `NSSplitViewItem`, so there is
/// no supported way to add an accessory to it. This view sits in the sidebar's
/// hierarchy, walks up to the split view, finds the item that contains it, and
/// installs the accessory once. Idempotent: if SwiftUI rebuilds the split, the
/// probe moves to the new window hierarchy and installs again; if the accessory
/// is already there it only refreshes the footer.
@available(macOS 26.0, *)
struct SidebarFooterAccessoryInstaller<Footer: View>: NSViewRepresentable {
    let footer: Footer

    func makeNSView(context: Context) -> ProbeView { ProbeView() }

    func updateNSView(_ view: ProbeView, context: Context) {
        // The footer's closure captures this window's state, so hand the
        // hosted view the fresh one on every update.
        view.footer = AnyView(footer)
        view.installIfPossible()
    }

    final class ProbeView: NSView {
        var footer = AnyView(EmptyView()) {
            didSet { accessory?.host.rootView = footer }
        }
        private weak var accessory: SidebarFooterAccessoryController?

        override func viewDidMoveToWindow() {
            super.viewDidMoveToWindow()
            installIfPossible()
        }

        func installIfPossible() {
            guard window != nil, let item = containingSplitViewItem() else { return }
            if let existing = item.bottomAlignedAccessoryViewControllers
                .lazy.compactMap({ $0 as? SidebarFooterAccessoryController }).first {
                accessory = existing
                existing.host.rootView = footer
                return
            }
            let controller = SidebarFooterAccessoryController(rootView: footer)
            item.addBottomAlignedAccessoryViewController(controller)
            accessory = controller
        }

        /// The split view item whose view contains this probe — the sidebar's.
        /// Found by containment, not by `splitViewItems.first`, so a split that
        /// ever gains a leading item cannot receive the footer by accident.
        private func containingSplitViewItem() -> NSSplitViewItem? {
            var view: NSView? = superview
            while let current = view {
                if let split = current as? NSSplitView,
                   let controller = split.delegate as? NSSplitViewController {
                    return controller.splitViewItems.first { isDescendant(of: $0.viewController.view) }
                }
                view = current.superview
            }
            return nil
        }
    }
}

@available(macOS 26.0, *)
final class SidebarFooterAccessoryController: NSSplitViewItemAccessoryViewController {
    let host: NSHostingView<AnyView>

    init(rootView: AnyView) {
        host = NSHostingView(rootView: rootView)
        super.init(nibName: nil, bundle: nil)
    }

    @available(*, unavailable)
    required init?(coder: NSCoder) { fatalError("init(coder:) is not supported") }

    override func loadView() {
        view = host
    }

    override func viewDidLoad() {
        super.viewDidLoad()
        // The style is settable from 26.1. On 26.0 the accessory still works and
        // the system picks the edge ("automatic").
        if #available(macOS 26.1, *) {
            preferredScrollEdgeEffectStyle = .soft
        }
    }
}
