import Foundation

// Probe: what does public API say while an iCloud placeholder downloads?
// usage: icloudprobe <path> [seconds]
let path = CommandLine.arguments[1]
let limit = Double(CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : "90") ?? 90
let url = URL(fileURLWithPath: path)
let t0 = Date()
func ts() -> String { String(format: "%6.2fs", Date().timeIntervalSince(t0)) }

let keys: [URLResourceKey] = [
    .ubiquitousItemDownloadingStatusKey, .ubiquitousItemIsDownloadingKey,
    .ubiquitousItemIsUploadingKey, .ubiquitousItemIsUploadedKey,
    .ubiquitousItemDownloadingErrorKey, .ubiquitousItemUploadingErrorKey,
    .fileSizeKey, .fileAllocatedSizeKey, .isUbiquitousItemKey,
]
func snap() -> String {
    var u = url; u.removeAllCachedResourceValues()
    guard let v = try? u.resourceValues(forKeys: Set(keys)) else { return "resourceValues threw" }
    var st = stat(); lstat(path, &st)
    let dataless = (st.st_flags & 0x40000000) != 0
    let status = v.ubiquitousItemDownloadingStatus?.rawValue.replacingOccurrences(of: "NSURLUbiquitousItemDownloadingStatus", with: "") ?? "nil"
    return "status=\(status) isDownloading=\(v.ubiquitousItemIsDownloading.map(String.init) ?? "nil") "
         + "uploading=\(v.ubiquitousItemIsUploading.map(String.init) ?? "nil") uploaded=\(v.ubiquitousItemIsUploaded.map(String.init) ?? "nil") "
         + "dlErr=\(v.ubiquitousItemDownloadingError.map { "\($0)" } ?? "nil") "
         + "size=\(v.fileSize ?? -1) allocated=\(v.fileAllocatedSize ?? -1) dataless=\(dataless)"
}

print("\(ts()) BEFORE \(snap())")

// NSMetadataQuery: the documented route to a percent.
let q = NSMetadataQuery()
q.searchScopes = [url.deletingLastPathComponent()]
q.predicate = NSPredicate(format: "%K == %@", NSMetadataItemFSNameKey, url.lastPathComponent)
func dumpQuery(_ tag: String) {
    q.disableUpdates()
    if q.resultCount == 0 { print("\(ts()) MDQ \(tag) results=0") }
    for case let item as NSMetadataItem in q.results {
        let pct = item.value(forAttribute: NSMetadataUbiquitousItemPercentDownloadedKey)
        let isDl = item.value(forAttribute: NSMetadataUbiquitousItemIsDownloadingKey)
        let st = item.value(forAttribute: NSMetadataUbiquitousItemDownloadingStatusKey)
        print("\(ts()) MDQ \(tag) percentDownloaded=\(String(describing: pct)) isDownloading=\(String(describing: isDl)) status=\(String(describing: st))")
    }
    q.enableUpdates()
}
for n in [NSNotification.Name.NSMetadataQueryDidFinishGathering, .NSMetadataQueryDidUpdate] {
    NotificationCenter.default.addObserver(forName: n, object: q, queue: .main) { _ in dumpQuery(n.rawValue.replacingOccurrences(of: "NSMetadataQuery", with: "")) }
}
print("\(ts()) MDQ start -> \(q.start())")

// The public, non-blocking trigger.
do { try FileManager.default.startDownloadingUbiquitousItem(at: url); print("\(ts()) startDownloadingUbiquitousItem OK") }
catch { print("\(ts()) startDownloadingUbiquitousItem threw: \(error)") }

var last = ""
let timer = Timer.scheduledTimer(withTimeInterval: 0.25, repeats: true) { t in
    let s = snap()
    if s != last { print("\(ts()) POLL \(s)"); last = s }
    if Date().timeIntervalSince(t0) > limit || s.contains("dataless=false") && s.contains("isDownloading=false") && s.contains("status=Current") {
        print("\(ts()) END \(s)"); exit(0)
    }
}
RunLoop.main.run()
