import SwiftUI

/// Toolbar pill shown while a sidebar drop is copying files into a project.
/// Plan §11: "title-bar pill shows progress + Cancel". Self-hides when no
/// copy is in flight.
///
/// Mirrors `PipelineActivityItem`'s visual envelope (Capsule + secondary
/// stroke) so the two pills feel like the same surface — only one is ever
/// visible at a time (cohort 1 doesn't drop onto a running project).
struct CopyProgressPill: View {
    @ObservedObject var copyMachinery: CopyMachinery
    @EnvironmentObject var i18n: I18n

    var body: some View {
        if let inFlight = copyMachinery.inFlight {
            pill(for: inFlight)
        }
    }

    @ViewBuilder
    private func pill(for inFlight: CopyMachinery.InFlight) -> some View {
        HStack(spacing: 6) {
            switch inFlight.phase {
            case .copying:
                Text(String(
                    format: i18n.t("desktop.chrome.copyingPill"),
                    inFlight.projectName
                ))
                .font(.system(.caption).weight(.medium))
                .lineLimit(1)
                ProgressView(value: inFlight.progress)
                    .progressViewStyle(.linear)
                    .frame(width: 80)
                Button {
                    copyMachinery.cancel()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .imageScale(.small)
                        .foregroundStyle(.secondary)
                }
                .buttonStyle(.plain)
                .help(i18n.t("common.buttons.cancel"))

            case .cancelling:
                Text(i18n.t("desktop.chrome.copyCancelling"))
                    .font(.system(.caption).weight(.medium))
                ProgressView().controlSize(.small)
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Capsule().fill(Color.secondary.opacity(0.08)))
        .overlay(Capsule().stroke(Color.secondary.opacity(0.25), lineWidth: 0.5))
        .contentShape(Capsule())
    }
}
