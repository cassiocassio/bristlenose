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
/// the difference between a confirmation and a speed bump. **A count that could
/// not be taken is not a zero**: the sheet appears, with one sentence in place
/// of the list (`ReAnalyseDecision`, decision #1, 21 Oct 2026).
///
/// **Stars are counted, and the drawing didn't have them.** `--clean` destroys
/// them along with everything else, so a list that omitted them would be silent
/// about a real loss — implementing the picture literally while breaking its
/// purpose. Added deliberately, 19 Aug 2026.
///
/// **The buttons follow the HIG, and did not at first.** Cancel led *and* held
/// `.defaultAction` while the confirm button carried `role: .destructive` —
/// three departures with one cause. Apple's alert guidance: don't make Cancel
/// the default; place the default on the trailing side; and reserve the
/// destructive style for actions people did *not* deliberately choose, Empty
/// Trash being their example of the case this sheet is in. Corrected 22 Aug
/// 2026. Pixels before and after:
/// `docs/mockups/reanalyse-sheet-pixels.html`.
///
/// **No folder paths, no `--clean`, no mention of an output directory.** A
/// researcher should never need a model of where Bristlenose keeps its working
/// files; the moment a message tells them to go and delete one, that model has
/// leaked.
/// What the sheet is about: the project, plus the measurements taken at the
/// moment of asking. `Identifiable` so `.sheet(item:)` can key on it.
///
/// `counts` is nil when the database could not be read — the sheet then says
/// it could not count, in place of the list.
struct PendingReAnalyse: Identifiable {
    let id = UUID()
    let project: Project
    let sessionCount: Int
    let counts: CurationCounts?
}

/// Whether **Re-analyse…** asks first, given what `CurationCountsReader.read`
/// returned. Pure, so the one branch that decides whether `--clean` runs
/// unasked is tested without a view.
///
/// **Unreadable confirms** (decision #1, 21 Oct 2026). A count that could not
/// be taken is not a zero: until then a database the app could not read ran
/// the destructive rebuild with no confirmation at all. A real zero still
/// proceeds — nothing of the researcher's to lose, so a modal would be a speed
/// bump.
enum ReAnalyseDecision: Equatable {
    case confirm(CurationCounts)
    case confirmUnreadable
    case proceed

    static func decide(_ counts: CurationCounts?) -> ReAnalyseDecision {
        guard let counts else { return .confirmUnreadable }
        return counts.isEmpty ? .proceed : .confirm(counts)
    }
}

struct ReAnalyseConfirmSheet: View {
    let projectName: String
    let sessionCount: Int
    /// Nil: the counts could not be read, and the sheet says so instead.
    let counts: CurationCounts?
    let onCancel: () -> Void
    let onConfirm: () -> Void

    @EnvironmentObject var i18n: I18n

    /// One line per kind, zero-count kinds omitted — a "0 tags" line is noise
    /// in a list whose whole job is to be read at a glance.
    private var lossLines: [String] {
        guard let counts else { return [] }
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

            if counts == nil {
                // The header promises a list, and an empty one under it would
                // read as "nothing to lose". One sentence in its place says the
                // count failed and what that risks.
                Text(i18n.t("desktop.chrome.reAnalyseLossUnknown"))
                    .font(.callout.weight(.medium))
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.vertical, 2)
            } else {
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
            }

            HStack {
                Spacer()
                // Cancel leads and takes Escape. Deliberately NOT the default —
                // the HIG's alert guidance says not to make Cancel the default
                // button, and offers "give no button the default" as the way to
                // stop people dismissing on Return without reading. It does not
                // offer "put the default on Cancel", which is what this sheet
                // did until 22 Aug 2026.
                Button(i18n.t("common.buttons.cancel"), action: onCancel)
                    .keyboardShortcut(.cancelAction)
                // The default, on the trailing side, and NOT destructive-styled.
                // The researcher chose Re-analyse… from a menu, so this button
                // performs their original intent — Apple's own Empty Trash case,
                // where the convenience of Return-to-confirm outweighs restating
                // that the action destroys. The destructive style is reserved
                // for actions people did not deliberately choose.
                // `AccountsSettingsView`'s Disconnect confirmation had already
                // applied this rule; this sheet was the outlier of three.
                Button(i18n.t("desktop.menu.project.reAnalyseConfirm"), action: onConfirm)
                    .keyboardShortcut(.defaultAction)
            }
            .padding(.top, 4)
        }
        .padding(22)
        .frame(width: 420)
    }
}
