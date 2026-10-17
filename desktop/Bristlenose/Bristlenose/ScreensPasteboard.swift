import Foundation

/// Which files a `screens-pasteboard-write` from the web view may put on the clipboard.
///
/// The message names a folder and file names; the web content is ours, but anything that reaches
/// the pasteboard from a bridge message is checked here first: the folder must be the open
/// project's exported screens folder, each name a plain `.jpg` in it, and the file must exist.
/// Anything else and nothing is written — a partial clipboard would paste a partial board — and
/// the refusal says why, for the log.
enum ScreensPasteboard {
    enum Refusal: String, Error {
        case noProject = "no project is open"
        case nothingToCopy = "no files were named"
        case notTheScreensFolder = "the folder is not the open project's screens folder"
        case notAPlainName = "a name is not a plain .jpg file name"
        case missingFile = "a named file is not there"
    }

    static func fileURLs(dir: String, files: [String], projectPath: String) -> Result<[URL], Refusal> {
        guard !projectPath.isEmpty else { return .failure(.noProject) }
        guard !files.isEmpty else { return .failure(.nothingToCopy) }
        let folder = URL(fileURLWithPath: dir).standardizedFileURL.resolvingSymlinksInPath()
        let project = URL(fileURLWithPath: projectPath).standardizedFileURL.resolvingSymlinksInPath()
        guard folder.lastPathComponent == "screens",
              folder.path.hasPrefix(project.path + "/") else { return .failure(.notTheScreensFolder) }
        var urls: [URL] = []
        for name in files {
            guard name == (name as NSString).lastPathComponent, !name.hasPrefix("."),
                  name.lowercased().hasSuffix(".jpg") else { return .failure(.notAPlainName) }
            let url = folder.appendingPathComponent(name)
            guard FileManager.default.fileExists(atPath: url.path) else { return .failure(.missingFile) }
            urls.append(url)
        }
        return .success(urls)
    }
}
