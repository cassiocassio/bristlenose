import SwiftUI
import UniformTypeIdentifiers

/// "Home" / empty-state surface shown in the detail pane when no project is
/// selected. Replaces the icon + two-line placeholder shipped in `4772c3a`
/// (called out in `100days.md` §2 Should as "an accidental engineering state,
/// not designed UX").
///
/// Two flavours:
/// - **`.firstRun`** — projects list is empty. Full welcome with two clear
///   next-actions (New Project, drop a folder) and a three-step "what
///   happens next" rail.
/// - **`.noSelection`** — projects exist but none is selected. Slimmer copy
///   ("Pick a project from the sidebar") — keeps the unused
///   `chrome.selectProject` locale key earning its keep.
struct WelcomeView: View {
    enum Variant {
        case firstRun
        case noSelection
    }

    let variant: Variant
    let onNewProject: () -> Void
    let onDropFolders: ([URL]) -> Void
    let onShowAIPrivacy: () -> Void

    @EnvironmentObject var i18n: I18n
    @State private var isDropTargeted = false

    var body: some View {
        switch variant {
        case .firstRun:
            firstRunBody
        case .noSelection:
            noSelectionBody
        }
    }

    // MARK: - First-run body

    private var firstRunBody: some View {
        VStack(spacing: 24) {
            Spacer(minLength: 24)

            Image(nsImage: NSApp.applicationIconImage)
                .resizable()
                .interpolation(.high)
                .frame(width: 112, height: 112)

            VStack(spacing: 6) {
                Text(i18n.t("desktop.chrome.welcomeTitle"))
                    .font(.system(.largeTitle, design: .default).weight(.semibold))
                Text(i18n.t("desktop.welcome.subtitle"))
                    .font(.title3)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .frame(maxWidth: 480)
            }

            actionRow
                .padding(.top, 4)

            stepsRail
                .padding(.top, 8)

            Button(i18n.t("desktop.welcome.aiPrivacyLink"), action: onShowAIPrivacy)
                .buttonStyle(.link)
                .font(.callout)
                .padding(.top, 4)

            Spacer(minLength: 24)
        }
        .padding(.horizontal, 32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - No-selection body

    private var noSelectionBody: some View {
        VStack(spacing: 16) {
            Image(systemName: "sidebar.left")
                .font(.system(size: 56, weight: .light))
                .foregroundStyle(.secondary)
            Text(i18n.t("desktop.chrome.noProjectSelected"))
                .font(.title2)
            Text(i18n.t("desktop.chrome.selectProject"))
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 380)
            // Cmd+N is owned by the File > New Project menu item, not by this
            // button — declaring it here would conflict with the menu and with
            // the firstRun variant's New Project card (three responders for
            // one shortcut, undefined SwiftUI resolution). Click still works.
            Button(i18n.t("desktop.welcome.newProject"), action: onNewProject)
                .controlSize(.large)
                .buttonStyle(.borderedProminent)
                .padding(.top, 4)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Action row (New Project + drop target)

    private var actionRow: some View {
        HStack(alignment: .top, spacing: 16) {
            // New Project card
            // Cmd+N owned by File > New Project menu (single source of truth).
            actionCard(
                systemImage: "plus.square.dashed",
                title: i18n.t("desktop.welcome.newProject"),
                subtitle: i18n.t("desktop.welcome.newProjectHint"),
                isPrimary: true,
                action: onNewProject
            )

            // Drop target card
            dropTargetCard
        }
        .frame(maxWidth: 520)
    }

    @ViewBuilder
    private func actionCard(
        systemImage: String,
        title: String,
        subtitle: String,
        isPrimary: Bool,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            VStack(alignment: .leading, spacing: 8) {
                Image(systemName: systemImage)
                    .font(.system(size: 28, weight: .light))
                    .foregroundStyle(isPrimary ? Color.accentColor : .secondary)
                Text(title)
                    .font(.headline)
                Text(subtitle)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(16)
            .background(
                RoundedRectangle(cornerRadius: 10)
                    .fill(Color(nsColor: .controlBackgroundColor))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 10)
                    .strokeBorder(Color(nsColor: .separatorColor), lineWidth: 0.5)
            )
        }
        .buttonStyle(.plain)
    }

    private var dropTargetCard: some View {
        VStack(alignment: .leading, spacing: 8) {
            Image(systemName: isDropTargeted ? "tray.and.arrow.down.fill" : "tray.and.arrow.down")
                .font(.system(size: 28, weight: .light))
                .foregroundStyle(isDropTargeted ? Color.accentColor : .secondary)
            Text(i18n.t("desktop.welcome.dropFolderTitle"))
                .font(.headline)
            Text(i18n.t("desktop.welcome.dropFolderHint"))
                .font(.callout)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(Color(nsColor: .controlBackgroundColor)
                    .opacity(isDropTargeted ? 0.6 : 1))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(
                    isDropTargeted ? Color.accentColor : Color(nsColor: .separatorColor),
                    style: StrokeStyle(
                        lineWidth: isDropTargeted ? 2 : 0.5,
                        dash: isDropTargeted ? [] : [4, 3]
                    )
                )
        )
        .onDrop(of: [UTType.fileURL], isTargeted: $isDropTargeted) { providers in
            Task {
                let urls = await Self.loadFileURLs(from: providers)
                let folders = urls.filter { $0.hasDirectoryPath }
                let payload = folders.isEmpty ? urls : folders
                await MainActor.run {
                    if !payload.isEmpty { onDropFolders(payload) }
                }
            }
            return true
        }
    }

    // MARK: - Steps rail

    private var stepsRail: some View {
        HStack(alignment: .top, spacing: 0) {
            stepCell(
                index: 1,
                systemImage: "folder",
                title: i18n.t("desktop.welcome.steps.ingestTitle"),
                detail: i18n.t("desktop.welcome.steps.ingestDetail")
            )
            stepDivider
            stepCell(
                index: 2,
                systemImage: "waveform.badge.magnifyingglass",
                title: i18n.t("desktop.welcome.steps.processTitle"),
                detail: i18n.t("desktop.welcome.steps.processDetail")
            )
            stepDivider
            stepCell(
                index: 3,
                systemImage: "doc.richtext",
                title: i18n.t("desktop.welcome.steps.exportTitle"),
                detail: i18n.t("desktop.welcome.steps.exportDetail")
            )
        }
        .frame(maxWidth: 640)
    }

    private var stepDivider: some View {
        Rectangle()
            .fill(Color(nsColor: .separatorColor))
            .frame(width: 0.5, height: 56)
            .padding(.top, 12)
    }

    private func stepCell(index: Int, systemImage: String, title: String, detail: String) -> some View {
        VStack(spacing: 6) {
            HStack(spacing: 6) {
                Text("\(index)")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
                    .frame(width: 14, height: 14)
                    .background(
                        Circle().stroke(Color(nsColor: .separatorColor), lineWidth: 0.5)
                    )
                Image(systemName: systemImage)
                    .font(.callout)
                    .foregroundStyle(.secondary)
            }
            Text(title)
                .font(.subheadline.weight(.medium))
            Text(detail)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity)
        .padding(.horizontal, 12)
    }

    // MARK: - URL loading helper

    private static func loadFileURLs(from providers: [NSItemProvider]) async -> [URL] {
        await withTaskGroup(of: URL?.self) { group in
            for provider in providers {
                group.addTask {
                    await withCheckedContinuation { continuation in
                        provider.loadItem(forTypeIdentifier: UTType.fileURL.identifier) { data, _ in
                            guard let data = data as? Data,
                                  let url = URL(dataRepresentation: data, relativeTo: nil) else {
                                continuation.resume(returning: nil)
                                return
                            }
                            continuation.resume(returning: url)
                        }
                    }
                }
            }
            var results: [URL] = []
            for await url in group {
                if let url { results.append(url) }
            }
            return results
        }
    }
}
