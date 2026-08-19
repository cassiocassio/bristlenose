import SwiftUI

// MARK: PII — UI-only, never log
// The project name rendered here may identify a client. Don't write it to
// os_log or any persisted channel.

/// The confirmation for a destructive rebuild — drawn in
/// `docs/mockups/analysis-lifecycle-states.html` §"The confirmation — measured,
/// not vague" before it was built, and matched to it here.
///
/// **A terse modal measures.** "This cannot be undone" tells a researcher
/// nothing they can weigh; five counted lines let them decide in one read. When
/// every count is zero there is nothing to weigh and no sheet appears at all —
/// the caller checks `CurationCounts.isEmpty` and simply starts the run. That is
/// the difference between a confirmation and a speed bump.
///
/// **Stars are counted, and the drawing didn't have them.** `--clean` destroys
/// them along with everything else, so a list that omitted them would be silent
/// about a real loss — implementing the picture literally while breaking its
/// purpose. Added deliberately, 19 Aug 2026.
///
/// **No folder paths, no `--clean`, no mention of an output directory.** A
/// researcher should never need a model of where Bristlenose keeps its working
/// files; the moment a message tells them to go and delete one, that model has
/// leaked.
/// What the sheet is about: the project, plus the measurements taken at the
/// moment of asking. `Identifiable` so `.sheet(item:)` can key on it.
struct PendingReAnalyse: Identifiable {
    let id = UUID()
    let project: Project
    let sessionCount: Int
    let counts: CurationCounts
}

struct ReAnalyseConfirmSheet: View {
    let projectName: String
    let sessionCount: Int
    let counts: CurationCounts
    let onCancel: () -> Void
    let onConfirm: () -> Void

    @EnvironmentObject var i18n: I18n

    /// One line per kind, zero-count kinds omitted — a "0 tags" line is noise
    /// in a list whose whole job is to be read at a glance.
    private var lossLines: [String] {
        var lines: [String] = []
        func add(_ key: String, _ n: Int) {
            guard n > 0 else { return }
            lines.append(i18n.plural("desktop.chrome.reAnalyseLoss.\(key)", count: n))
        }
        add("editedQuotes", counts.editedQuotes)
        add("tags", counts.tags)
        add("starred", counts.starredQuotes)
        add("renamedSpeakers", counts.renamedSpeakers)
        add("namedThemes", counts.namedThemes)
        return lines
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            Image(systemName: "arrow.clockwise")
                .font(.system(size: 26))
                .foregroundStyle(.secondary)

            Text(i18n.t("desktop.chrome.reAnalyseConfirmTitle", ["project": projectName]))
                .font(.headline)

            Text(i18n.plural("desktop.chrome.reAnalyseRebuild", count: sessionCount))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            VStack(alignment: .leading, spacing: 3) {
                Text(i18n.t("desktop.chrome.reAnalyseLossHeader"))
                    .font(.callout.weight(.medium))
                ForEach(lossLines, id: \.self) { line in
                    Text(line)
                        .font(.callout)
                        .foregroundStyle(.secondary)
                        .padding(.leading, 12)
                }
            }
            .padding(.vertical, 2)

            HStack {
                Spacer()
                // Cancel is the default: the researcher arrived from a menu item
                // ending in an ellipsis, not from a button labelled "throw this
                // away", so Return must not finish the sentence for them.
                Button(i18n.t("common.buttons.cancel"), action: onCancel)
                    .keyboardShortcut(.defaultAction)
                // Destructive role, and no shortcut: the only key that finishes
                // this sheet is Escape, and Escape cancels.
                Button(i18n.t("desktop.menu.project.reAnalyseConfirm"),
                       role: .destructive, action: onConfirm)
            }
            .padding(.top, 4)
        }
        .padding(22)
        .frame(width: 420)
    }
}
