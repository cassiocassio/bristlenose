# iCloud progress probe

What does public API report while an iCloud placeholder downloads? Answers row 73 of
`docs/design-cloud-files.md` ("How far along is the fetch?").

```
swiftc -O icloudprobe.swift -o icloudprobe
./icloudprobe "<path to a dataless file in iCloud Drive>" 120
```

Re-evict the file first (Finder ▸ Remove Download), or it is already local and the run shows nothing.
It starts the fetch with `FileManager.startDownloadingUbiquitousItem` and polls the iCloud
`URLResourceKey`s, the allocated size and the `SF_DATALESS` flag every 250 ms, with an
`NSMetadataQuery` alongside for the percent attributes.

## Measured

**macOS 27.0 (26A428), 5 Nov 2026, run from Terminal (not sandboxed), one 135 MB PDF:**
`isDownloading` went true 0.6 s after the call and false at the end. Allocated size jumped 0 to full
size (no gradual growth). `NSMetadataQuery` returned the item with every percent/status attribute
`nil` and sent no update. So: a yes/no flag, no percent.

Not measured: the sandboxed app, other macOS versions, other providers. Log:
`probe-macos-27.0-26A428.log`. Compare a 27.2 run against it.
