# Apple Voice Memos (.m4a): when did the recording start?

Research for the session-start tool. Read-only, metadata only; no audio was read.
Measured 11 Oct 2026 on this Mac (macOS 27, Darwin 27.0.0).

Labels: **MEASURED** (here, this session), **DOCUMENTED** (vendor or primary source), **REPORTED** (third party, community, forensic write-up).

## What could not be measured

- `~/Library/Group Containers/group.com.apple.VoiceMemos.shared/Recordings/`: **`ls` is refused with "Operation not permitted"** (TCC). Stat-ing a named path inside it works (`CloudRecordings.db` exists), but listing the folder does not. MEASURED.
- `CloudRecordings.db`: `sqlite3 -readonly` fails with **"authorization denied"**. MEASURED.
- `~/Library/Application Support/com.apple.voicememos/Recordings/` (the pre-Catalina location) does not exist on this Mac. MEASURED.
- So **no original, unexported Voice Memos file and no ZDATE were measured.** Part B steps 2–4 stopped there, as the brief asks. A bundled, sandboxed Bristlenose would hit the same TCC wall, so the tool will almost never see the originals anyway: it sees **exported/shared copies** (below).
- No other Voice Memos file is indexed on this Mac. The `.m4a` files Spotlight finds are WhatsApp (`AUDIO-YYYY-MM-DD-…`), Photos system resources and test fixtures. MEASURED.

## Measurement: the exported copy (`~/Downloads/New Recording.m4a`)

Not an iCloud placeholder (`st_flags = 0x0`). The quarantine xattr names **Mail** as the agent, so this copy was shared from Voice Memos by email and saved from Mail.

| Field | Value | Source |
|---|---|---|
| filename | `New Recording.m4a` (the default title; no timestamp) | MEASURED |
| `ftyp` | major `M4A `, compatible `M4A isommp42` | MEASURED |
| box order | `ftyp`, `mdat`, `moov` (moov at the **end**) | MEASURED (atom walk) |
| codec | AAC, 48 kHz, mono | MEASURED |
| duration | 364.650667 s (6 min 4.65 s) | MEASURED |
| `creation_time` (format, = `mvhd`) | 2026-07-23 **12:06:16Z** | MEASURED |
| `mvhd` / `tkhd` / `mdhd` created and modified | all six identical, 12:06:16Z | MEASURED |
| stream `handler_name` | `Core Media Audio` | MEASURED |
| `udta/meta/ilst` | **only** `----:com.apple.iTunes:iTunSMPB` (gapless info) | MEASURED |
| `encoder` / `com.apple.VoiceMemos …` | **absent** | MEASURED |
| `date` / `©day` / `com.apple.quicktime.*` | **absent** | MEASURED |
| `tsrp` (transcript atom) | absent | MEASURED |
| `st_birthtime` = `st_mtime` | 2026-07-23 12:10:43Z (13:10:43 BST) | MEASURED |
| `kMDItemContentCreationDate` | 12:10:43Z (mirrors birthtime) | MEASURED |
| quarantine timestamp = `kMDItemDateAdded` | 12:15:58Z (when it was saved out of Mail) | MEASURED |

Arithmetic (MEASURED, then INFERRED):

- `creation_time + duration` = 12:06:16 + 6:04.65 = **12:12:20.65Z**.
- The file already existed at **12:10:43Z** (birthtime, which Mail set before the 12:15:58 save; most likely the message time). A recording cannot have ended after its file existed, so **the recording started no later than 12:04:38Z**.
- So `creation_time` (12:06:16Z) is **not the start**. It is at least 98 s after the latest possible start.
- It fits **either** of two readings, and one file cannot separate them:
  1. **End of recording**: start = 12:00:11Z, end 12:06:16, mailed 12:10:43.
  2. **Export time**: the share sheet re-encoded the file at 12:06:16, and the recording ended some time before.
- Reading 2 is favoured by the container's shape: moov after mdat, all six box dates identical, handler `Core Media Audio`, no Voice Memos encoder and no `date` tag. That is the signature of an AVFoundation export/re-mux, not of the recorder's own file (see the documented tags below). INFERRED.
- Caveat: the phone's clock and Mail's date are both involved. Normal NTP skew is under a second, far below the 98 s margin.

**Conclusion for the exported copy:** none of its timestamps is the start. `creation_time` is the end or the export time, and the filesystem dates are the transfer/save time. The only safe bound is **start ≤ birthtime − duration**, and it is an upper bound, not a value.

## Documentation and reports

### On-disk naming (originals)
- Originals are named `YYYYMMDD HHMMSS-XXXXXXXX.m4a`, e.g. `20131215 074938-73C33C1E.m4a`. REPORTED: [Apple Community 252094028](https://discussions.apple.com/thread/252094028). An older form without the hex suffix, `20170321 155824.m4a`, is also REPORTED ([Apple Community 8366771](https://discussions.apple.com/thread/8366771)).
- The filename is the recording's creation time. The *recording time* Voice Memos shows is the **start**, **in the iPhone's local time zone**. REPORTED: [Forensic originality identification of iPhone's voice memos (ResearchGate)](https://www.researchgate.net/publication/337598372_Forensic_originality_identification_of_iPhone's_voice_memos). The same paper says the time is in the file's metadata on iOS 8 but **not on iOS 10+** (contradicted by the `date` tag reported below for iOS 18).
- The time under a memo in the app is "the time you started the recording". REPORTED: [Apple Community 8585529](https://discussions.apple.com/thread/8585529).
- **Not measured.** Whether the filename's clock is local or UTC could not be confirmed against a ZDATE here. Treat "local" as REPORTED, not MEASURED.

### Share / export
- A new recording is titled "New Recording" (numbered after the first), or the **location name** if Location Services is on. DOCUMENTED: [Apple Support, iPhone Voice Memos](https://support.apple.com/guide/iphone/make-a-recording-iph4d2a39a3b/ios), [Export to Files](https://support.apple.com/guide/iphone/export-a-recording-to-files-iph831c37815/ios).
- Exported files get the title as filename and "a new time stamp, generated when the export happens". REPORTED: [Apple Community 252094028](https://discussions.apple.com/thread/252094028); also [Apple Community 253965723](https://discussions.apple.com/thread/253965723) (repeat "Save to Files" gives wrong modified dates) and [mp3tag community](https://community.mp3tag.de/t/macos-voice-memo-m4a-files-recording-date/55855) ("export date as Creation Date").
- MEASURED above: the Mail-shared copy carries the default title and **no** Voice Memos provenance tags.

### Container tags written by Voice Memos (originals)
- `encoder` = `com.apple.VoiceMemos (iPhone Version 18.5 (Build 22F76))`, a `date` tag such as `2025-06-08T08:46:16Z` (**UTC**, `Z`), and a custom `tsrp` atom holding the transcript JSON. REPORTED: [Thomas Countz, 2025](https://thomascountz.com/2025/06/08/unlocking-apple-voice-memo-transcripts). The post does not say whether `date` is the start or the end.
- `com.apple.VoiceMemos (iPhone Version 17.2.1)` as encoder, and the m4a creation date compared to the DB "with microseconds set to zero". REPORTED: [voice-memo-forensics](https://github.com/fdelorenzi/voice-memo-forensics). That tool expects the DB date and the file's creation date to match, which implies they record the same instant. It does not say which instant.
- Recording date in `QuickTime:CreateDate` / `TrackCreateDate`; `©day` unused. REPORTED: [mp3tag community](https://community.mp3tag.de/t/macos-voice-memo-m4a-files-recording-date/55855).
- **Start versus end for `creation_time` on originals: no source states it.** Searches found none. In general, AVFoundation writers stamp `mvhd` when the movie is finalised, and Apple camera video carries `com.apple.quicktime.creationdate` separately for the start. For Voice Memos neither has been shown.

### Trim, replace, resume, Enhance
- Trim/Replace offer "Save Recording" (**overwrites the original**) or "Save as New Recording" (a new file). DOCUMENTED: [Apple Support, Mac](https://support.apple.com/guide/voice-memos/edit-a-recording-vmac7e39c22e/mac), [Apple Support, iPhone](https://support.apple.com/guide/iphone/edit-or-delete-a-recording-iphc9bdaee83/ios).
- What an overwrite or a new copy does to the filename, `creation_time`, `date` or ZDATE: **not found**. "Enhance Recording": **not found**. Resume-recording (Replace from the end): **not found**. UNKNOWN. Assume any edit can rewrite `mvhd` dates, and that a "new recording" copy gets a new filename time.
- The DB duration and the file duration usually differ slightly. REPORTED: [voice-memo-forensics](https://github.com/fdelorenzi/voice-memo-forensics).

### CloudRecordings.db
- Table `ZCLOUDRECORDING` with `ZDATE`, `ZDURATION`, `ZPATH`, `ZCUSTOMLABEL` (title), `ZUNIQUEID`, `ZFOLDER`, `ZENCRYPTEDTITLE`. Database in WAL mode; copy it with `-wal`/`-shm` before reading. REPORTED: [voice-memo-forensics](https://github.com/fdelorenzi/voice-memo-forensics), [ResearchGate figure](https://www.researchgate.net/figure/The-database-structure-of-the-Voice-Memos-in-the-iOS-12_fig1_337598372).
- Export scripts use `ZDATE` (Core Data epoch, 2001-01-01 UTC) as "the date it was created". REPORTED: [Apple Community 255955065](https://discussions.apple.com/thread/255955065). Start versus end is not stated.
- MEASURED: TCC blocks it here.

## Recommended rule

**Recognising a Voice Memos file**

1. **Original (strong):** the filename matches `^\d{8} \d{6}(-[0-9A-F]{8})?\.m4a$` **and/or** `encoder` starts with `com.apple.VoiceMemos`. Either alone is good; both together are conclusive.
2. **Exported copy (weak):** no encoder, no `date` tag, `ftyp` `M4A `, `handler_name` `Core Media Audio`, `iTunSMPB` only, moov after mdat, and a filename like `New Recording( \d+)?.m4a` or a place name. This signature is generic AVFoundation export, **not** Voice Memos specifically. Never treat it as a provenance claim.

**Getting the start**

1. **Filename time is the start**, as wall-clock time in the recording device's zone (REPORTED, not MEASURED). It has no offset in it. Pair it with the `date` tag (UTC) when present to recover the offset, or fall back to the machine's zone and say so.
2. **`date` tag (UTC):** use it when present, but its start/end meaning is **unverified**. If the filename is also present, compare them: equal (± offset to the whole hour/half hour) means `date` is the start; a difference of about the duration means it is the end. One measurement on an original would settle this.
3. **`creation_time` / `mvhd`:** do **not** use it as the start. On the one measured file it was at least 98 s after the latest possible start (the end or the export time). If nothing else exists, **`creation_time − duration`** is a better estimate than `creation_time`, but label it inferred.
4. **Filesystem birthtime/mtime on an exported copy is the transfer/save time.** It is only an upper bound: start ≤ birthtime − duration.
5. **ZDATE:** authoritative in principle, unreachable in practice (TCC, and Bristlenose never sees the user's library). Don't design around it.
6. **An exported copy with none of 1–2 has no recoverable start.** Say so, rather than presenting `creation_time` as when the interview began.

## Owed: one measurement settles most of this

With Full Disk Access granted to a terminal, for 5–10 originals: filename time vs `date` vs `creation_time` vs ZDATE vs ZDURATION. Also, once each: a trimmed memo saved in place, an Enhanced memo, and a resumed memo.
