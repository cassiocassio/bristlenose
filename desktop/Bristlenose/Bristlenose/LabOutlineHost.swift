#if DEBUG
import AppKit
import SwiftUI

/// Hosts the shipping `SidebarOutlineController` with only the knobs a lab
/// varies. Mirrors `ProjectSidebarOutline.updateNSViewController` minus the
/// app services (runner, copy, cloud import), which are optional on the
/// controller — a lab that wants one hands it over in `configure`.
///
/// Shared by Sidebar Lab (scroll geometry, no services) and Review Gallery
/// (row states, a throwaway runner and live data). Moved out of
/// `SidebarLabView.swift` so the second lab hosts the real controller rather
/// than a copy of this wrapper.
struct LabOutlineHost: NSViewControllerRepresentable {
    let index: ProjectIndex
    let i18n: I18n
    let roots: [OutlineNode]
    @Binding var selection: Set<SidebarSelection>
    let activeTab: Tab?
    let floats: Bool
    let scrolls: Bool
    let onActivateLens: (Tab) -> Void
    let onContentHeight: ((CGFloat) -> Void)?
    let onController: (SidebarOutlineController) -> Void
    /// Runs before every `update(...)`, so whatever it sets (a runner, live
    /// data, a report crash, the exporting project) is in place for the
    /// reload that draws the rows. The controller holds its services weakly:
    /// whatever this hands over must be retained by the closure's captures.
    var configure: ((SidebarOutlineController) -> Void)? = nil

    func makeNSViewController(context: Context) -> SidebarOutlineController {
        let controller = SidebarOutlineController()
        controller.projectIndex = index
        controller.i18n = i18n
        DispatchQueue.main.async { onController(controller) }
        return controller
    }

    func updateNSViewController(_ controller: SidebarOutlineController, context: Context) {
        controller.projectIndex = index
        controller.i18n = i18n
        configure?(controller)
        controller.onSelectionChange = { new in
            if selection != new { selection = new }
        }
        controller.onActivateLens = onActivateLens
        controller.update(roots: roots, selection: selection, activeTab: activeTab, lensesEnabled: true)

        let outlineView = controller.outlineView
        outlineView.floatsGroupRows = floats
        if let sv = outlineView.enclosingScrollView {
            sv.hasVerticalScroller = scrolls
            sv.verticalScrollElasticity = scrolls ? .automatic : .none
            // A fixed block must not inherit titlebar insets it never sits under.
            sv.automaticallyAdjustsContentInsets = scrolls
            if !scrolls { sv.contentInsets = NSEdgeInsetsZero }
        }
        if let onContentHeight, outlineView.numberOfRows > 0 {
            let h = outlineView.rect(ofRow: outlineView.numberOfRows - 1).maxY
            DispatchQueue.main.async { onContentHeight(ceil(h)) }
        }
    }
}
#endif
