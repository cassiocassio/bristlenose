import AppKit
import Foundation
import OSLog
import UserNotifications

private let bannerLog = Logger(subsystem: "app.bristlenose", category: "run-banner")

// MARK: - The seam to macOS

enum RunBannerAuthorization: Equatable {
    case notDetermined
    case denied
    case allowed
}

/// Everything that touches the system's notification centre, so the rest can be
/// tested without one.
@MainActor
protocol RunBannerSystem: AnyObject {
    func authorization() async -> RunBannerAuthorization
    /// The system's own request. It prompts only once; later calls do not.
    func requestAuthorization() async -> Bool
    func registerCategories(placeholders: [RunBannerCategory: String])
    func post(identifier: String, threadID: String, projectID: UUID, text: RunBannerText) async
}

/// The one-button screen before the system's request (Apple's rules for such a
/// screen: a single "Continue" that opens the system's alert, and no Cancel).
@MainActor
protocol RunBannerPreAlerting: AnyObject {
    func present(i18n: I18n) async
}

extension Notification.Name {
    /// Posted when the researcher clicks a run banner. `userInfo["projectID"]`
    /// is the project's id as a string: nothing else rides in the notification.
    static let runBannerClicked = Notification.Name("bristlenoseRunBannerClicked")
}

// MARK: - The coordinator

/// Decides, once per run end, whether to post a banner, and asks for permission
/// at the right moment. It posts only when the researcher is not looking.
@MainActor
final class RunBannerCoordinator: RunBannerNoting {

    private let system: RunBannerSystem
    private let preAlert: RunBannerPreAlerting
    private let i18n: I18n
    private let attention: () -> ResearcherAttention
    private let isOn: () -> Bool

    /// Runs already posted this launch. Apple re-alerts when a request reuses an
    /// identifier, so the identifier cannot be the dedupe.
    private var posted: Set<String> = []
    private var askedThisLaunch = false

    init(
        system: RunBannerSystem,
        preAlert: RunBannerPreAlerting,
        i18n: I18n,
        attention: @escaping () -> ResearcherAttention,
        isOn: @escaping () -> Bool = { RunBannerPreference.isOn() }
    ) {
        self.system = system
        self.preAlert = preAlert
        self.i18n = i18n
        self.attention = attention
        self.isOn = isOn
    }

    // MARK: Permission

    /// Asked only from a researcher-initiated start, only while the system has
    /// not been asked, only once per launch, and never when the researcher has
    /// switched the banner off. A decline is final: the system will not prompt
    /// again, and neither do we.
    func researcherStartedRun() {
        guard isOn(), !askedThisLaunch else { return }
        askedThisLaunch = true
        Task { @MainActor in
            guard await system.authorization() == .notDetermined else { return }
            await preAlert.present(i18n: i18n)
            _ = await system.requestAuthorization()
        }
    }

    // MARK: A run ended

    func runDidEnd(
        projectID: UUID, projectName: String, state: PipelineState,
        terminus: EventLogReader.Event?, stopRequested: Bool, runKey: String
    ) {
        guard isOn(),
              let plan = RunBanner.plan(for: state, terminus: terminus, stopRequested: stopRequested)
        else { return }
        guard !posted.contains(runKey) else { return }
        // The researcher is in the app and can see the row change: nothing to say.
        guard !attention().isLooking else { return }
        posted.insert(runKey)

        let text = plan.text(projectName: projectName, i18n: i18n)
        Task { @MainActor in
            guard await system.authorization() == .allowed else {
                bannerLog.info("run banner not posted — notifications are not allowed")
                return
            }
            system.registerCategories(placeholders: [
                .finished: i18n.t("desktop.runBanner.finished"),
                .didntFinish: i18n.t("desktop.chrome.failedTitle"),
            ])
            await system.post(
                identifier: runKey, threadID: projectID.uuidString, projectID: projectID, text: text)
        }
    }
}

// MARK: - The real system

@MainActor
final class SystemRunBannerSystem: RunBannerSystem {

    private var center: UNUserNotificationCenter { .current() }

    func authorization() async -> RunBannerAuthorization {
        switch await center.notificationSettings().authorizationStatus {
        case .notDetermined: return .notDetermined
        case .denied: return .denied
        case .authorized, .provisional, .ephemeral: return .allowed
        @unknown default: return .denied
        }
    }

    func requestAuthorization() async -> Bool {
        (try? await center.requestAuthorization(options: [.alert, .sound])) ?? false
    }

    func registerCategories(placeholders: [RunBannerCategory: String]) {
        let categories = placeholders.map { category, placeholder in
            UNNotificationCategory(
                identifier: category.rawValue, actions: [], intentIdentifiers: [],
                hiddenPreviewsBodyPlaceholder: placeholder, options: [])
        }
        center.setNotificationCategories(Set(categories))
    }

    func post(identifier: String, threadID: String, projectID: UUID, text: RunBannerText) async {
        let content = UNMutableNotificationContent()
        content.title = text.title
        content.body = text.body
        content.sound = .default
        content.threadIdentifier = threadID
        content.categoryIdentifier = text.category.rawValue
        // The project's id only: no name and no path ride in the notification's
        // own data, so the click can find the project and nothing else can.
        content.userInfo = ["projectID": projectID.uuidString]
        let request = UNNotificationRequest(identifier: identifier, content: content, trigger: nil)
        do {
            try await center.add(request)
        } catch {
            bannerLog.error("run banner add failed: \(error.localizedDescription, privacy: .public)")
        }
    }
}

/// Must be set before `applicationDidFinishLaunching` returns: a banner entry
/// outlives the app, and a click on it relaunches us and delivers its response
/// to whatever delegate exists by then.
final class RunBannerNotificationDelegate: NSObject, UNUserNotificationCenterDelegate {

    static let shared = RunBannerNotificationDelegate()

    /// The coordinator has already decided the researcher is not looking, so
    /// when the system still counts the app as foreground, present anyway.
    func userNotificationCenter(
        _ center: UNUserNotificationCenter, willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .list, .sound])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        if response.actionIdentifier == UNNotificationDefaultActionIdentifier,
           let id = response.notification.request.content.userInfo["projectID"] as? String {
            NotificationCenter.default.post(
                name: .runBannerClicked, object: nil, userInfo: ["projectID": id])
        }
        completionHandler()
    }
}

// MARK: - The one-button screen

@MainActor
final class NSAlertRunBannerPreAlert: RunBannerPreAlerting {
    func present(i18n: I18n) async {
        let alert = NSAlert()
        alert.messageText = i18n.t("desktop.runBanner.prealert.title")
        // "Settings > General", in the words the Settings window itself uses.
        let path = i18n.t("settings.heading") + " > " + i18n.t("desktop.settingsTabs.general")
        alert.informativeText = i18n.t("desktop.runBanner.prealert.body", ["path": path])
        alert.addButton(withTitle: i18n.t("desktop.runBanner.prealert.continue"))
        if let window = PanelHost.window {
            _ = await alert.beginSheetModal(for: window)
        } else {
            _ = alert.runModal()
        }
    }
}

// MARK: - Is the researcher looking?

/// Tracks what AppKit's own state cannot say: whether the display is asleep, the
/// screen is locked, or the login session is in the background. An active app
/// with its window visible is still not being looked at in any of those.
///
/// The sleep and session notifications are documented. The lock pair
/// (`com.apple.screenIsLocked`) is widely used and not documented by Apple.
@MainActor
final class ScreenState {
    private(set) var displayIsAwake = true
    private(set) var screenIsUnlocked = true
    private(set) var sessionIsActive = true
    private var tokens: [(NotificationCenter, NSObjectProtocol)] = []

    init(
        workspace: NotificationCenter = NSWorkspace.shared.notificationCenter,
        distributed: NotificationCenter = DistributedNotificationCenter.default()
    ) {
        observe(workspace, NSWorkspace.screensDidSleepNotification) { $0.displayIsAwake = false }
        observe(workspace, NSWorkspace.screensDidWakeNotification) { $0.displayIsAwake = true }
        observe(workspace, NSWorkspace.sessionDidResignActiveNotification) { $0.sessionIsActive = false }
        observe(workspace, NSWorkspace.sessionDidBecomeActiveNotification) { $0.sessionIsActive = true }
        observe(distributed, Notification.Name("com.apple.screenIsLocked")) { $0.screenIsUnlocked = false }
        observe(distributed, Notification.Name("com.apple.screenIsUnlocked")) { $0.screenIsUnlocked = true }
    }

    deinit { for (center, token) in tokens { center.removeObserver(token) } }

    private func observe(
        _ center: NotificationCenter, _ name: Notification.Name,
        _ apply: @escaping @MainActor (ScreenState) -> Void
    ) {
        let token = center.addObserver(forName: name, object: nil, queue: .main) { [weak self] _ in
            MainActor.assumeIsolated { if let self { apply(self) } }
        }
        tokens.append((center, token))
    }

    func attention(app: NSApplication = .shared) -> ResearcherAttention {
        ResearcherAttention(
            appIsActive: app.isActive,
            windowIsVisible: app.occlusionState.contains(.visible),
            displayIsAwake: displayIsAwake,
            screenIsUnlocked: screenIsUnlocked,
            sessionIsActive: sessionIsActive)
    }
}
