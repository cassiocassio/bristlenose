import SwiftUI

/// The "lens" rail — five mode rows above the project List that relocate the
/// former toolbar tab Picker into the sidebar (spec §2, §3.1, §5).
///
/// IMPORTANT — this is deliberately a `VStack` of `Button`s, NOT a `List`/`Form`.
/// Two AppKit helpers locate the project list by "the first NSTableView in the
/// window": `SidebarDeselectMonitor` (empty-click deselect) and
/// `ContentView.focusProjectsList` (the ⌘0 keyboard no-trap). A `List`/`Form`
/// here would inject a *second* `NSTableView` above the project one and silently
/// break both. Keep this Button/VStack-based.
struct LensRail: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n
    /// Dimmed until a project is selected + ready — mirrors the former Picker's
    /// `.disabled(selectedProject == nil || !bridgeHandler.isReady)`. The dimming
    /// *is* the "pick a project first" teaching (spec §3.1).
    let isEnabled: Bool

    var body: some View {
        VStack(spacing: 1) {
            ForEach(LensItem.all) { item in
                LensRow(bridgeHandler: bridgeHandler, i18n: i18n, item: item)
            }
        }
        .disabled(!isEnabled)
    }
}

/// One lens row. Active iff `bridgeHandler.activeTab == item.tab` (nil→`.project`,
/// matching the former toolbar Picker's tab binding). Renders deliberately
/// lighter than a project row — accent-tinted symbol + medium-weight label + a subtle
/// selection capsule ("toolbar-toggle language", spec §3.1).
///
/// Active-state is *derived* from `bridgeHandler.activeTab`, not held in a
/// separate `@State`: an in-report link-nav updates the route (→ `activeTab`)
/// but would not touch a separate `@State`, so deriving keeps the lit lens
/// truthful. `@ObservedObject` is required so the row re-tints on route change.
private struct LensRow: View {
    @ObservedObject var bridgeHandler: BridgeHandler
    @ObservedObject var i18n: I18n
    let item: LensItem

    private var isActive: Bool {
        (bridgeHandler.activeTab ?? .project) == item.tab
    }

    var body: some View {
        Button {
            bridgeHandler.switchToTab(item.tab)
        } label: {
            Label {
                Text(item.label(i18n))
                    .fontWeight(isActive ? .medium : .regular)
            } icon: {
                Image(systemName: item.systemImage)
                    .foregroundStyle(isActive ? AnyShapeStyle(.tint) : AnyShapeStyle(.secondary))
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .foregroundStyle(isActive ? AnyShapeStyle(.primary) : AnyShapeStyle(.secondary))
            .padding(.vertical, 4)
            .padding(.horizontal, 8)
            .background {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .fill(Color.accentColor.opacity(isActive ? 0.14 : 0))
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(isActive ? [.isSelected] : [])
    }
}
