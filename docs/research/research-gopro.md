# GoPro MP4 time metadata: what the camera writes, and what it means

Researched 11 Oct 2026. Evidence labels:
- **MEASURED**: read from a real GoPro file in this session.
- **DOCUMENTED**: from GoPro's own repos or docs, URL given.
- **REPORTED**: from forums or third-party writing, URL given.
- **INFERRED**: my reasoning from the above, not confirmed.

## Samples measured

Six real camera files from `gopro/gpmf-parser/samples/` (3.7–11.6 MB each), saved in
the samples (not committed — re-download from the URLs below): `hero5.mp4`, `hero6.mp4`, `hero7.mp4`, `hero8.mp4`,
`max-heromode.mp4`, `Fusion.mp4`. Raw ffprobe output is in `samples/gopro/probe.txt`, and
the extracted GPMF streams are the `*.gpmd` files beside it.
Source: https://github.com/gopro/gpmf-parser/tree/main/samples

**The samples stop at HERO8 and the 2019 MAX. Nothing here is measured for HERO9–HERO13.**
gpmf-parser publishes no newer sample.

Command: `ffprobe -v error -print_format json -show_entries format=duration:format_tags:stream_tags <file>`

### hero5.mp4 (MEASURED)
```
format: duration 34.576208
  major_brand=mp41  minor_version=538120216  compatible_brands=mp41
  creation_time=2017-04-17T10:31:43.000000Z
  location=+33.1265-117.3274/   location-eng=+33.1265-117.3274/
  firmware=HD5.02.02.00.00
stream video avc1: creation_time=2017-04-17T10:31:43.000000Z language=eng
                   handler_name="\tGoPro AVC" encoder="GoPro AVC encoder" timecode=10:31:06:01
stream audio mp4a: same creation_time, handler_name="\tGoPro AAC", timecode=10:31:06:01
stream data  tmcd: same creation_time, handler_name="\tGoPro TCD", timecode=10:31:06:01
stream data  gpmd: same creation_time, handler_name="\tGoPro MET"
stream data  fdsc: same creation_time, handler_name="\tGoPro SOS"
```

### All six, condensed (MEASURED)
| file | firmware | format creation_time | timecode (ffprobe) | duration | first GPSU (GPMF, UTC) |
|---|---|---|---|---|---|
| hero5 | HD5.02.02.00.00 | 2017-04-17T10:31:43Z | 10:31:06:01 @23.976 | 34.58 | 2017-04-17 17:31:03.000 |
| hero6 | HD6.01.01.60.00 | 2018-01-24T11:27:32Z | 11:26:51:05 @29.97 | 23.59 | 2018-01-24 19:27:58.674 |
| hero7 | HD7.01.01.80.00 | 2016-01-01T02:27:42Z | 02:27:33:15 | 12.71 | 2019-11-18 23:42:08.755 |
| hero8 | HD8.01.01.20.00 | 2019-11-18T15:41:25Z | 15:40:28:28 | 12.68 | 2019-11-18 23:42:08.645 |
| MAX (hero mode) | H19.03.01.30.00 | 2019-11-18T15:45:32Z | 15:44:35:10 | 10.54 | 2019-11-18 23:45:14.000 |
| Fusion | FS1.04.01.70.00 | 2017-12-31T12:15:25Z | 12:14:41:16 | 15.17 | 2018-03-23 17:25:37.375 |

Things that hold in every file:
- **`creation_time` is identical on the format and on all five streams.** There is no second
  time to choose between.
- **`handler_name` values are `GoPro AVC`, `GoPro AAC`, `GoPro TCD`, `GoPro MET`, `GoPro SOS`.**
  They carry a leading length byte: `\t` (0x09) on HERO5 and Fusion, `\x0b` plus two
  trailing spaces on HERO6 and later. Strip control characters and whitespace before
  comparing. HEVC models are reported to write `GoPro H.265` (REPORTED; not in these samples).
- **`encoder` is `GoPro AVC encoder`**, on the video stream only.
- **`firmware` is a format tag.** Its prefix identifies the model: `HD5.`, `HD6.`, `HD7.`,
  `HD8.`, `H19.` (MAX), `FS1.` (Fusion). Later models are reported to use `H21.` (HERO10),
  `H22.` (HERO11), and so on (REPORTED).
- **The streams are `avc1` + `mp4a` + `tmcd` + `gpmd` + `fdsc`.** The `gpmd` codec tag is the
  GPMF telemetry stream.
- **`location` (ISO 6709) appears only when GPS had a fix** (hero5, hero6, MAX, Fusion). It
  is absent on hero7 and hero8.
- **GPMF device names (`DVNM`) are `Camera`, `Hero6 Black`, `Hero7 Black`, `HERO8 Black`,
  `GoPro Max`, `Fusion`.**
- **There is no `TZON` (timezone) tag in any of these files**, neither in `udta` nor in the
  GPMF stream.

## Q1. Which tags does ffprobe show?
**MEASURED**: see the tables above. Format tags: `major_brand=mp41`,
`minor_version=538120216`, `compatible_brands=mp41`, `creation_time`, optional
`location`/`location-eng`, `firmware`. Stream tags: `creation_time`, `language=eng`,
`handler_name`, `encoder` (video only), and `timecode` (video, audio and tmcd).
ffprobe does **not** show the GPMF clock (`GPSU`, `GPS9`) or `TZON`; you have to parse the
`gpmd` stream or the `udta` GPMF box to get those.

## Q2. Local clock labelled `Z`, or true UTC?

**Verdict: local wall-clock time, mislabelled UTC.** MEASURED on HERO5, HERO6, HERO8 and MAX;
DOCUMENTED by GoPro Labs; REPORTED widely.

**MEASURED.** The GPMF `GPSU` tag is genuine UTC from the GPS receiver.
Each sample was shot at GoPro HQ in Carlsbad, California (location +33.13 −117.33).
`creation_time` minus `GPSU` is about **−7 h** on the April file (Pacific Daylight Time) and
about **−8 h** on the January and November files (Pacific Standard Time). That is exactly
the local offset, so the `Z` is false.

Two further measured hazards:
- **Unset clocks.** hero7 reads `2016-01-01`, the clock-reset default, while its own GPS says
  2019-11-18. Fusion reads 2017-12-31 against a GPS date of 2018-03-23.
- **Drift.** Even where the clock was set, it disagreed with GPS by **−44 s to +40 s**:
  hero5 +40 s, hero6 −27 s, hero8 −44 s, MAX +18 s.
  - Caveat: GPSU on older models is 1 Hz and can lag the fix. The minute-scale part of that
    drift is INFERRED to be real clock drift rather than GPS lag.

**DOCUMENTED** by GoPro Labs, "GPS Time Synchronization"
(https://gopro.github.io/labs/control/gpssync/):
- On HERO9 and HERO10, a GPS fix updates only the minutes and seconds of the camera clock,
  "it preserves your current timezone offset."
- "On HERO11, the camera has a timezone control, so GPS time can be used fully."
- So the camera has a timezone setting from **HERO11** on. Before HERO11 it has none: the
  clock is simply local time.

**DOCUMENTED** by gpmf-parser's README (https://github.com/gopro/gpmf-parser):
- `TZON` is a header metadata field holding an "offset in minutes" (example −480). From the
  timeline above, it is likely HERO11 and later only.
- `GPSU` holds UTC time from GPS, from HERO5 Black on, at 1 Hz.
- `GPS9` (HERO11 and HERO13) carries days-since-2000 and seconds-since-midnight at 10 Hz.
- **HERO12 has no GPS receiver**, so it has neither `GPSU` nor `GPS9`.

**DOCUMENTED** by ExifTool's GoPro tag table (https://exiftool.org/TagNames/GoPro.html): it
names `TZON` → `TimeZone`, `CDAT` → `CreationDate`, `GPSU` → `GPSDateTime`, and
`GPS9[6]` → `GPSDateTime`.

**REPORTED** in forums:
- GoPro writes local time to the QuickTime fields without an offset, and Google Photos and
  Lightroom then shift it by the viewer's zone.
  - GoPro community: https://community.gopro.com/s/question/0D53b00008BtZOLCA3/storing-local-time-rather-than-utc-in-video-exif-data?language=en_US
  - Lightroom bug thread: https://community.adobe.com/bug-reports-674/p-video-capture-time-shifted-by-time-zone-offset-663853/index5.html
- ExifTool assumes no zone by default. Its `-api QuickTimeUTC` option treats these values as
  UTC, and the documented GoPro fix is
  `exiftool -GlobalTimeShift +<offset> -api QuickTimeUTC …`
  (https://exiftool.org/TagNames/QuickTime.html).
- Immich's date/timezone megathread also covers GoPro
  (https://github.com/immich-app/immich/discussions/12650).

**Does the Quik app set the clock?** REPORTED (setup guides, the GoPro community): pairing
with Quik sets the camera's date and time from the phone, in the phone's **local** time.
On HERO11 and later it also sets the timezone. Not verified first-hand.

**Unverified:** whether HERO11 and later still write local time to `creation_time` (with
`TZON` alongside) or switch to true UTC. No HERO11+ sample was available.
- GoPro staff's reply in https://github.com/gopro/labs/discussions/533 ("set your timezone to
  GMT", "This is no issue if you don't change the timezone") implies the clock stays a local
  clock.
- Treat it as local until a HERO11+ file is measured.

## Q3. Start or end of recording?

**Verdict: START**, truncated to the whole second, in the camera's own clock.
MEASURED on all six files. **That this holds for every chapter of a chaptered recording is
INFERRED.**

**The `tmcd` timecode is also a start time.** gpmf-parser documents the tmcd track as the
"starting timecode (time of day as frame since midnight)".

**ffprobe's rendering of it is about 0.1% slow.** The tmcd frame count runs at the
NTSC rate (30000/1001 or 24000/1001), but ffprobe formats it as if the rate were the whole
number (30 or 24). Multiply the displayed time of day by 1001/1000 and it matches
`creation_time` in every file:

| file | timecode as shown | × 1001/1000 | creation_time | difference |
|---|---|---|---|---|
| hero5 | 10:31:06.0 | 10:31:43.9 | 10:31:43 | −0.9 s |
| hero6 | 11:26:51.2 | 11:27:32.4 | 11:27:32 | −0.4 s |
| hero7 | 02:27:33.5 | 02:27:42.4 | 02:27:42 | −0.4 s |
| hero8 | 15:40:28.9 | 15:41:25.4 | 15:41:25 | −0.4 s |
| MAX | 15:44:35.3 | 15:45:32.0 | 15:45:32 | 0.0 s |
| Fusion | 12:14:41.5 | 12:15:25.6 | 12:15:25 | −0.6 s |

So `creation_time` = recording start, in the camera clock. If it were the end time, it would
sit 10–35 s later than this.

**Trap:** don't use ffprobe's `timecode` string directly as the time of day. It reads 37–57 s
early by afternoon, and the error grows through the day.

**GPS check where the clock was set (hero8 and MAX).** The first GPSU falls within ±1 min of
`creation_time`, consistent with drift, not with an end time. The MAX first GPSU is 18 s
before `creation_time` and the clip is only 10.5 s long. So against the GPS clock the
camera can even read later than the true end, which is why the drift caveat matters more
than start-versus-end.

**Chapters: INFERRED, not measured.** GoPro splits a recording at about 4 GB into
`GX01nnnn`, `GX02nnnn`, ….
- Each chapter is a self-contained MP4 with its own tmcd start timecode. The chaptered-merge
  write-ups say the merged result keeps the start time
  (https://www.trekview.org/blog/join-gopro-chaptered-split-video-files-preserve-telemetry/).
- So each chapter's `creation_time` is most likely the start of **that chapter**, not of the
  session.
- **The session start is chapter 01's `creation_time`.** For chapter N, the expected value
  is chapter 01's start plus the durations of chapters 1 to N−1. Check that, rather than
  assume it.
- No chaptered sample was available.

## Q4. Filename convention

DOCUMENTED in GoPro's "File Naming Convention" article
(https://community.gopro.com/s/article/GoPro-Camera-File-Naming-Convention); the page did not
render here, so this is per its search snippet and other write-ups such as
https://havecamerawilltravel.com/action/gopro-split-video-files/:
- **HERO6 and later:** `GHccnnnn.MP4` (H.264/AVC) or `GXccnnnn.MP4` (H.265/HEVC).
  - `cc` = chapter, 01–99; `nnnn` = recording number, 0001–9999.
  - Example: `GX010042.MP4`, `GX020042.MP4`.
- **HERO5 and earlier:** `GOPRnnnn.MP4` is the first chapter; later chapters are
  `GPccnnnn.MP4`, with chapter numbering starting at 01 for the second segment.
- **MAX 360 footage:** `GSccnnnn.360`.
- **Sidecars:** `GL…LRV` (low-resolution proxy) and `GH…THM` / `GX…THM` (thumbnail), with the
  same numbering.
- **There is no time in the name.** The number is a counter, and can reset or collide across
  cards and cameras. It is useful only for grouping chapters: same `nnnn` and prefix, ordered
  by `cc`.

## Recommended rule

**Recognise a GoPro file** (any one is enough; two together is strong):
1. A stream `handler_name` that, stripped of control characters and whitespace, starts with
   `GoPro ` (`GoPro AVC`, `GoPro H.265`, `GoPro AAC`, `GoPro TCD`, `GoPro MET`).
2. A data stream with `codec_tag_string == "gpmd"`.
3. A `firmware` format tag matching `^(HD\d|H\d\d|FS\d)\.`.
4. A video `encoder` tag starting `GoPro`.
5. Supporting evidence only: a filename matching `^(G[HXSP]\d{6}|GOPR\d{4})\.(MP4|360)$`
   (case-insensitive).

**Turn `creation_time` into a start instant:**
1. **Take `creation_time` as the START**, not the end. Don't subtract the duration.
2. **Discard the `Z`. Treat the value as a naive local wall-clock time.** Never treat it as
   UTC.
3. **Resolve the zone, best first:**
   1. **GPMF `GPSU` / `GPS9`**, if present (HERO5–HERO11 and HERO13 with GPS on). This is
      true UTC.
      - Use the first fix as the start instant, minus its payload offset.
      - Better: `zone_offset = round_to_15min(creation_time_naive − first_GPSU)`. That gives
        the zone and absorbs clock drift, and it rescues unset clocks too: hero7's
        2016-01-01 is fixed by GPSU.
      - Costs a gpmd parse (≈1 KB/s of telemetry, trivially cheap).
   2. **The `TZON` header** (HERO11+), if present: minutes east of UTC.
      `instant = creation_time_naive − TZON`. This needs measuring on a real HERO11+ file
      before it is trusted, and so does its sign.
   3. **Otherwise** the zone is unknown. Interpret in the researcher's or project's zone and
      say so. This is the only honest default for HERO5–HERO10 and HERO12 without GPS. Do
      not claim minute precision: drift of ±1 min was measured even on set clocks.
4. **Plausibility guard.**
   - A date of 2016-01-01 (or any date before the model's release) means an unset clock.
   - Fall back to GPS if present; otherwise report the start as unknown rather than wrong.
5. **Chapters.**
   - Group by prefix plus `nnnn`. The session start is the `cc=01` file's start.
   - Check that the later chapters' starts ≈ chapter 01 plus the cumulative durations.
6. **Don't read the ffprobe `timecode` string as a time of day** without the ×1001/1000
   correction on NTSC-rate footage. It carries no zone either.

Sources: https://github.com/gopro/gpmf-parser · https://gopro.github.io/labs/control/gpssync/ ·
https://github.com/gopro/labs/discussions/533 · https://exiftool.org/TagNames/GoPro.html ·
https://exiftool.org/TagNames/QuickTime.html ·
https://community.gopro.com/s/question/0D53b00008BtZOLCA3/storing-local-time-rather-than-utc-in-video-exif-data?language=en_US ·
https://community.adobe.com/bug-reports-674/p-video-capture-time-shifted-by-time-zone-offset-663853/index5.html ·
https://github.com/immich-app/immich/discussions/12650 ·
https://www.trekview.org/blog/join-gopro-chaptered-split-video-files-preserve-telemetry/ ·
https://havecamerawilltravel.com/action/gopro-split-video-files/
