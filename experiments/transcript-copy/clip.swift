// Put the Markdown (plain) and HTML flavours on the pasteboard together,
// as the browser's copy handler would.  swift clip.swift <md> <html>
import AppKit
let a = CommandLine.arguments
let md = try! String(contentsOfFile: a[1], encoding: .utf8)
let htm = try! String(contentsOfFile: a[2], encoding: .utf8)
let pb = NSPasteboard.general
pb.clearContents()
pb.setString(md, forType: .string)
pb.setString(htm, forType: .html)
print(pb.types ?? [])
