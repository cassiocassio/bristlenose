import SwiftUI

/// Toolbar pill + popovers for the on-device model setup flow (flow B,
/// model-first). Self-hides when the `OllamaDownloadModel` is idle. Mirrors
/// `CopyProgressPill`'s visual envelope (Capsule + secondary stroke) so the
/// two pills read as the same surface.
///
/// The pill is a click target; the popover it opens is phase-driven, so a
/// single presentation walks the user through `choosingModel` → `needsOllama`
/// → `waitingForOllama` → `downloading` → `finishing` without re-anchoring.
/// Honesty rule (made visible): the hourglass NEVER animates (we're waiting on
/// the human); only the download bar and the "Bristlenose-is-working" spinner
/// move. Red is reserved for the genuine `failed` state.
///
/// See `docs/design-ollama-setup.md` for the full spec and
/// `docs/mockups/ollama-setup-popovers.html` for the frozen copy + widths.
struct OllamaDownloadPill: View {
    @ObservedObject var model: OllamaDownloadModel
    @EnvironmentObject var i18n: I18n
    @State private var showingDetail = false

    var body: some View {
        if model.isActive {
            Button {
                showingDetail.toggle()
            } label: {
                pillBody
            }
            .buttonStyle(.plain)
            .accessibilityLabel(statusText)
            .accessibilityValue(accessibilityValueText)
            .popover(isPresented: $showingDetail, arrowEdge: .bottom) {
                detailPopover
            }
            // Auto-present the picker once when the pill first appears
            // post-consent. The 350ms delay lets the toolbar settle so the
            // popover anchors to the pill, not to where it briefly wasn't.
            .task(id: model.pendingAutoPresent) {
                guard model.pendingAutoPresent else { return }
                try? await Task.sleep(for: .milliseconds(350))
                guard !Task.isCancelled, model.pendingAutoPresent else { return }
                showingDetail = true
                model.consumeAutoPresent()
            }
        }
    }

    // MARK: - Pill

    @ViewBuilder
    private var pillBody: some View {
        HStack(spacing: 6) {
            icon
            Text(statusText)
                .font(.system(.caption).weight(.medium))
                .lineLimit(1)
            progressAccessory
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .background(Capsule().fill(Color.secondary.opacity(0.08)))
        .overlay(Capsule().stroke(Color.secondary.opacity(0.25), lineWidth: 0.5))
        .contentShape(Capsule())
    }

    @ViewBuilder
    private var icon: some View {
        switch model.phase {
        case .choosingModel, .needsOllama, .waitingForOllama:
            // Static hourglass — we're waiting on the human, not moving bytes.
            Image(systemName: "hourglass")
                .imageScale(.small)
                .foregroundStyle(.secondary)
        case .downloading, .finishing:
            Image(systemName: "arrow.down.circle")
                .imageScale(.small)
                .foregroundStyle(.secondary)
        case .failed:
            Image(systemName: "xmark.circle.fill")
                .imageScale(.small)
                .foregroundStyle(.red)
        case .idle:
            EmptyView()
        }
    }

    @ViewBuilder
    private var progressAccessory: some View {
        switch model.phase {
        case .downloading where model.totalBytes > 0:
            ProgressView(value: model.downloadRatio)
                .progressViewStyle(.linear)
                .frame(width: 58)
            Text(model.downloadRatio.formatted(.percent.precision(.fractionLength(0))))
                .font(.caption)
                .monospacedDigit()
                .foregroundStyle(.secondary)
        case .downloading, .finishing:
            // A pull we don't yet have byte totals for, and the post-pull
            // settle, get a spinner — never a fake determinate bar.
            ProgressView()
                .controlSize(.small)
        default:
            EmptyView()
        }
    }

    // MARK: - Popover

    @ViewBuilder
    private var detailPopover: some View {
        switch model.phase {
        case .choosingModel:
            ModelPicker(model: model)
                .environmentObject(i18n)
        case .needsOllama:
            needsOllamaPopover
        case .waitingForOllama:
            waitingPopover
        case .downloading:
            downloadingPopover
        case .finishing:
            finishingPopover
        case .failed(let failure):
            failedPopover(failure)
        case .idle:
            EmptyView()
        }
    }

    private var needsOllamaPopover: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(String(format: i18n.t("desktop.ollamaSetup.needsTitle"), modelName))
                .font(.system(.callout).weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
            Text(i18n.t("desktop.ollamaSetup.needsBody"))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                Button(i18n.t("desktop.ollamaSetup.getOllamaButton")) {
                    // No dismiss — the popover follows the phase to waiting.
                    model.getOllama()
                }
                .keyboardShortcut(.defaultAction)
            }
            .padding(.top, 6)
        }
        .padding(16)
        .frame(width: 280)
    }

    private var waitingPopover: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(i18n.t("desktop.ollamaSetup.waitingTitle"))
                .font(.system(.callout).weight(.semibold))
            Text(LocalizedStringKey(i18n.t("desktop.ollamaSetup.waitingBody")))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            VStack(alignment: .leading, spacing: 4) {
                stepRow(1, i18n.t("desktop.ollamaSetup.waitingStep1"))
                stepRow(2, i18n.t("desktop.ollamaSetup.waitingStep2"))
            }
            Text(String(format: i18n.t("desktop.ollamaSetup.waitingFootnote"), modelName))
                .font(.footnote)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.top, 2)
            Divider()
                .padding(.top, 4)
            HStack(spacing: 8) {
                // Static hourglass — passive wait, no spinner.
                Image(systemName: "hourglass")
                    .imageScale(.small)
                    .foregroundStyle(.secondary)
                Text(i18n.t("desktop.ollamaSetup.waitingStatusLabel"))
                    .font(.callout)
                    .foregroundStyle(.secondary)
                Spacer()
                Button(i18n.t("common.buttons.cancel")) {
                    model.cancel()
                }
                .controlSize(.small)
            }
        }
        .padding(16)
        .frame(width: 280)
    }

    private var downloadingPopover: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(String(format: i18n.t("desktop.ollamaSetup.downloadingTitle"), modelName))
                .font(.system(.callout).weight(.semibold))
                .fixedSize(horizontal: false, vertical: true)
            if model.totalBytes > 0 {
                Text(byteString)
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .monospacedDigit()
                ProgressView(value: model.downloadRatio)
                    .progressViewStyle(.linear)
            } else {
                HStack {
                    ProgressView()
                        .controlSize(.small)
                    Spacer()
                }
            }
            HStack {
                Spacer()
                Button(i18n.t("common.buttons.cancel")) {
                    model.cancel()
                }
            }
            .padding(.top, 6)
        }
        .padding(16)
        .frame(width: 280)
    }

    private var finishingPopover: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(i18n.t("desktop.ollamaSetup.finishingTitle"))
                .font(.system(.callout).weight(.semibold))
            Text(String(format: i18n.t("desktop.ollamaSetup.finishingBody"), modelName))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                ProgressView()
                    .controlSize(.small)
                Spacer()
            }
            .padding(.top, 6)
        }
        .padding(16)
        .frame(width: 280)
    }

    private func failedPopover(_ failure: OllamaDownloadModel.Failure) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(i18n.t("desktop.ollamaSetup.failedTitle"))
                .font(.system(.callout).weight(.semibold))
            Text(failureDetail(failure))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)
            HStack {
                Spacer()
                Button(i18n.t("common.buttons.retry")) {
                    // No dismiss — retry re-enters downloading in place.
                    model.retry()
                }
                .keyboardShortcut(.defaultAction)
            }
            .padding(.top, 6)
        }
        .padding(16)
        .frame(width: 280)
    }

    private func stepRow(_ n: Int, _ text: String) -> some View {
        HStack(alignment: .top, spacing: 6) {
            Text("\(n).")
                .font(.callout)
                .foregroundStyle(.secondary)
                .monospacedDigit()
            Text(text)
                .font(.callout)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
    }

    // MARK: - Strings

    private var statusText: String {
        switch model.phase {
        case .choosingModel:
            return i18n.t("desktop.ollamaSetup.pillChoosingModel")
        case .needsOllama:
            return i18n.t("desktop.ollamaSetup.pillNeedsOllama")
        case .waitingForOllama:
            return i18n.t("desktop.ollamaSetup.pillWaiting")
        case .downloading:
            return model.totalBytes > 0
                ? String(format: i18n.t("desktop.ollamaSetup.pillDownloading"), modelName)
                : i18n.t("desktop.ollamaSetup.pillDownloadingNoModel")
        case .finishing:
            return i18n.t("desktop.ollamaSetup.pillFinishing")
        case .failed:
            return i18n.t("desktop.ollamaSetup.pillFailed")
        case .idle:
            return ""
        }
    }

    /// VoiceOver value: download percentage while a determinate pull is in
    /// flight; empty otherwise (the label alone carries indeterminate phases).
    private var accessibilityValueText: String {
        if case .downloading = model.phase, model.totalBytes > 0 {
            return model.downloadRatio.formatted(.percent.precision(.fractionLength(0)))
        }
        return ""
    }

    /// Humanised model name from the catalog (e.g. "Gemma 4 E4B"), falling
    /// back to the raw tag for custom values.
    private var modelName: String {
        let tag = model.currentTag ?? ""
        return OllamaCatalog.model(for: tag)?.displayName ?? tag
    }

    private var byteString: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        let done = formatter.string(fromByteCount: model.completedBytes)
        let total = formatter.string(fromByteCount: model.totalBytes)
        return String(format: i18n.t("desktop.ollamaSetup.bytesProgress"), done, total)
    }

    private func failureDetail(_ failure: OllamaDownloadModel.Failure) -> String {
        switch failure {
        case .noInternet:
            return i18n.t("desktop.ollamaSetup.failNoInternet")
        case .timedOut:
            return i18n.t("desktop.ollamaSetup.failTimedOut")
        case .cantReach:
            return i18n.t("desktop.ollamaSetup.failCantReach")
        case .generic(let message):
            return String(format: i18n.t("desktop.ollamaSetup.failGeneric"), message)
        }
    }
}

// MARK: - Model picker (step 1)

/// The `choosingModel` popover: a 360pt radio list of the curated catalogue,
/// grouped by install state when the daemon is already up. Selecting a row and
/// pressing "Use …" commits via `confirmModel(tag:)`; the popover then follows
/// the phase the commit routes to.
private struct ModelPicker: View {
    @ObservedObject var model: OllamaDownloadModel
    @EnvironmentObject var i18n: I18n
    @State private var selectedTag: String

    init(model: OllamaDownloadModel) {
        self.model = model
        _selectedTag = State(initialValue: model.currentTag ?? OllamaCatalog.recommendedTag())
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(i18n.t("desktop.ollamaSetup.chooseTitle"))
                .font(.system(.callout).weight(.semibold))

            Text(String(format: bodyTemplate, ramString))
                .font(.callout)
                .foregroundStyle(.secondary)
                .fixedSize(horizontal: false, vertical: true)

            modelsBox

            if OllamaCatalog.isLowDisk() {
                Label(i18n.t("desktop.ollamaSetup.lowDisk"),
                      systemImage: "exclamationmark.triangle")
                    .font(.system(.caption).weight(.medium))
                    .foregroundStyle(.red)
            }

            // Foreshadow only while the daemon is unprobed/down — once we know
            // Ollama is up, naming "next steps" would be misleading.
            if model.installedSnapshot == nil {
                Text(LocalizedStringKey(i18n.t("desktop.ollamaSetup.foreshadow")))
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(8)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(
                        RoundedRectangle(cornerRadius: 7)
                            .fill(Color.secondary.opacity(0.06)))
            }

            HStack {
                Spacer()
                Button(String(format: i18n.t("desktop.ollamaSetup.useModel"),
                              selectedDisplayName)) {
                    // No dismiss — the popover follows confirmModel's routing.
                    model.confirmModel(tag: selectedTag)
                }
                .keyboardShortcut(.defaultAction)
            }

            if selectedTagInstalled {
                Text(i18n.t("desktop.ollamaSetup.chooseInstalledCaption"))
                    .font(.caption)
                    .foregroundStyle(.tertiary)
                    .frame(maxWidth: .infinity, alignment: .center)
            }
        }
        .padding(16)
        .frame(width: 360)
    }

    // MARK: Rows

    private var modelsBox: some View {
        VStack(spacing: 0) {
            if isGrouped {
                groupHeader(i18n.t("desktop.ollamaSetup.groupInstalled"))
                rowGroup(installedCurated, installed: true)
                groupHeader(i18n.t("desktop.ollamaSetup.groupDownload"))
                rowGroup(notInstalledCurated, installed: false)
            } else {
                rowGroup(OllamaCatalog.curated, installed: false)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 8))
        .overlay(
            RoundedRectangle(cornerRadius: 8)
                .stroke(Color(nsColor: .separatorColor), lineWidth: 0.5))
    }

    @ViewBuilder
    private func rowGroup(_ models: [OllamaModel], installed: Bool) -> some View {
        ForEach(Array(models.enumerated()), id: \.element.id) { index, m in
            if index > 0 { Divider() }
            rowView(m, installed: installed)
        }
    }

    @ViewBuilder
    private func rowView(_ m: OllamaModel, installed: Bool) -> some View {
        let disabled = !OllamaCatalog.fits(m)
        let selected = selectedTag == m.tag
        HStack(alignment: .top, spacing: 9) {
            radio(selected: selected, disabled: disabled)
                .padding(.top, 1)
            VStack(alignment: .leading, spacing: 2) {
                descriptor(for: m, installed: installed)
                Text(subline(for: m, installed: installed))
                    .font(.caption)
                    .foregroundStyle(disabled ? .tertiary : .secondary)
                    .monospacedDigit()
            }
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 9)
        .background(selected ? Color.accentColor.opacity(0.06) : Color.clear)
        .contentShape(Rectangle())
        .onTapGesture {
            if !disabled { selectedTag = m.tag }
        }
    }

    @ViewBuilder
    private func radio(selected: Bool, disabled: Bool) -> some View {
        if disabled {
            Image(systemName: "circle").foregroundStyle(.tertiary)
        } else if selected {
            Image(systemName: "circle.inset.filled").foregroundStyle(Color.accentColor)
        } else {
            Image(systemName: "circle").foregroundStyle(.secondary)
        }
    }

    private func groupHeader(_ text: String) -> some View {
        HStack {
            Text(text)
                .font(.system(.caption2).weight(.semibold))
                .foregroundStyle(.tertiary)
                .textCase(.uppercase)
            Spacer()
        }
        .padding(.horizontal, 11)
        .padding(.top, 7)
        .padding(.bottom, 4)
    }

    /// Composed descriptor: bold model name, then dot-separated qualifiers.
    /// Uses `.foregroundColor` (returns `Text`) so the parts concatenate.
    private func descriptor(for m: OllamaModel, installed: Bool) -> Text {
        let disabled = !OllamaCatalog.fits(m)
        var line = Text(m.displayName)
            .font(.callout.weight(.semibold))
            .foregroundColor(disabled ? Color(nsColor: .tertiaryLabelColor) : .primary)

        func qualifier(_ s: String, color: Color = .secondary) -> Text {
            Text(" · " + s).font(.callout).foregroundColor(color)
        }

        if installed {
            line = line + qualifier(i18n.t("desktop.ollamaSetup.tagReady"))
        } else {
            line = line + qualifier(tierWord(m.tier))
            if disabled {
                let needs = String(
                    format: i18n.t("desktop.ollamaSetup.rowNeedsRam"), "\(Int(m.minRAMGB))")
                line = line + qualifier(needs, color: .red)
            } else if m.tag == OllamaCatalog.recommendedTag() {
                line = line + qualifier(i18n.t("desktop.ollamaSetup.tagRecommended"))
            } else if m.tier == .smallest {
                line = line + qualifier(i18n.t("desktop.ollamaSetup.tagFastest"))
            }
        }
        return line
    }

    private func subline(for m: OllamaModel, installed: Bool) -> String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .file
        if installed {
            let bytes = (model.installedSnapshot ?? [])
                .first { $0.name == m.tag }?.sizeBytes ?? 0
            return String(
                format: i18n.t("desktop.ollamaSetup.rowOnDisk"),
                formatter.string(fromByteCount: bytes))
        } else {
            let bytes = Int64(m.weightsGB * 1_000_000_000)
            return String(
                format: i18n.t("desktop.ollamaSetup.rowDownloadSize"),
                formatter.string(fromByteCount: bytes))
        }
    }

    private func tierWord(_ tier: OllamaModel.Tier) -> String {
        switch tier {
        case .smallest: return i18n.t("desktop.ollamaSetup.tagSmallest")
        case .balanced: return i18n.t("desktop.ollamaSetup.tagBalanced")
        case .best: return i18n.t("desktop.ollamaSetup.tagBest")
        }
    }

    // MARK: Derived state

    private var installedTags: Set<String> {
        Set((model.installedSnapshot ?? []).map(\.name))
    }

    private var installedCurated: [OllamaModel] {
        OllamaCatalog.curated.filter { installedTags.contains($0.tag) }
    }

    private var notInstalledCurated: [OllamaModel] {
        OllamaCatalog.curated.filter { !installedTags.contains($0.tag) }
    }

    private var hasInstalled: Bool { !installedCurated.isEmpty }

    /// Group into "Already on this Mac" / "Download" only when we've probed the
    /// daemon AND at least one curated model is already on disk.
    private var isGrouped: Bool {
        model.installedSnapshot != nil && hasInstalled
    }

    private var bodyTemplate: String {
        hasInstalled
            ? i18n.t("desktop.ollamaSetup.chooseBodyHasInstalled")
            : i18n.t("desktop.ollamaSetup.chooseBody")
    }

    private var selectedTagInstalled: Bool {
        installedTags.contains(selectedTag)
    }

    private var selectedDisplayName: String {
        OllamaCatalog.model(for: selectedTag)?.displayName ?? selectedTag
    }

    /// System RAM as "16 GB" — `.memory` count style is 1024-based, so a
    /// 16 GB Mac reads "16 GB" rather than the 17.18 a decimal style gives.
    private var ramString: String {
        let formatter = ByteCountFormatter()
        formatter.countStyle = .memory
        formatter.allowedUnits = [.useGB]
        return formatter.string(
            fromByteCount: Int64(ProcessInfo.processInfo.physicalMemory))
    }
}
