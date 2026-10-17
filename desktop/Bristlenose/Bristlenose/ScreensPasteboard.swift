import Foundation

/// Which files a `screens-pasteboard-write` from the web view may put on the clipboard.
///
/// The message names a folder and file names; the web content is ours, but anything that reaches
/// the pasteboard from a bridge message is checked here first: the folder must be the open
/// project's exported screens folder, each name a plain `.jpg` in it, and the file must exist.
/// Anything else and nothing is written — a partial clipboard would paste a partial board.
enum ScreensPasteboard {
    static func fileURLs(dir: String, files: [String], projectPath: String) -> [URL]? {
        guard !projectPath.isEmpty, !files.isEmpty else { return nil }
        let folder = URL(fileURLWithPath: dir).standardizedFileURL.resolvingSymlinksInPath()
        let project = URL(fileURLWithPath: projectPath).standardizedFileURL.resolvingSymlinksInPath()
        guard folder.lastPathComponent == "screens",
              folder.path.hasPrefix(project.path + "/") else { return nil }
        var urls: [URL] = []
        for name in files {
            guard name == (name as NSString).lastPathComponent, !name.hasPrefix("."),
                  name.lowercased().hasSuffix(".jpg") else { return nil }
            let url = folder.appendingPathComponent(name)
            guard FileManager.default.fileExists(atPath: url.path) else { return nil }
            urls.append(url)
        }
        return urls
    }
}
