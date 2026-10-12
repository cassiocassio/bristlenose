# Zoom Corporation recorders: when did the recording start?

Research for a recording-start-time detector. Zoom here is the hardware maker (H/F/M/PodTrak series), not the meeting app.
Researched 11 Oct 2026.

Evidence labels:
- **MEASURED**: run here, against a real file, with ffprobe 8.1.1 or a Python chunk walker.
- **DOCUMENTED**: an official manual or spec says so. URL given.
- **REPORTED**: a third party says so. URL given.
- **INFERRED**: my reasoning, not verified.

Samples and manual PDFs were downloaded for the measurement and are not committed — re-download from the URLs below.

---

## 0. Real files obtained (MEASURED)

| Local file | Source | Device |
|---|---|---|
| `H_ZOOM0001.WAV`, `H_ZOOM0002.WAV`, `H_ZOOM0025.WAV` (0.5–6 MB) | Git-LFS objects in `UNFDanmark/GDC2017-GR1`, path `lyd memes my friend/Optaget lyde/skrald/` (fetched through media.githubusercontent.com) | **ZOOM H1** (original H1), **clock never set** |
| `F8_Tr1.WAV`, `F8_TrL_R.WAV`, `F8_MULTI.WAV` (1.7, 3.3, 16 MB) | wavinfo test fixtures, https://github.com/iluvcapra/wavinfo/tree/master/tests/test_files/zoom_F8 | **ZOOM F8**, firmware 1.10, clock set, timecode running |

### ffprobe output, verbatim (`ffprobe -v error -print_format json -show_entries format=duration:format_tags`)

H1, unset clock (`H_ZOOM0002.WAV`):
```json
"duration": "10.916667",
"tags": {
  "encoded_by": "ZOOM Handy Recorder H1",
  "date": "2010-01-01",
  "creation_time": "01:15:44",
  "time_reference": "436224000",
  "coding_history": "A=PCM,F=96000,W=24,M=stereo,T=ZOOM Handy Recorder H1"
}
```
The other two H1 files show `00:00:04` / `384000` and `01:28:23` / `509088000`, all dated `2010-01-01`.

F8 (`F8_Tr1.WAV`; the MULTI and TrL_R files carry the same date, time and reference):
```json
"duration": "11.000000",
"tags": {
  "comment": "SPEED=25.000ND\r\nTAKE=001\r\nUBITS=00000000\r\nSCENE=Scene_1_2AG\r\nTAPE=WINFO\r\nCIRCLED=FALSE\r\nTRL=TrL\r\nTRR=TrR\r\nTR1=Tr1\r\n…NOTE=Test 01 wavinfo\r\n",
  "encoded_by": "ZOOM F8",
  "date": "2019-02-13",
  "creation_time": "22:40:18",
  "time_reference": "3917280000",
  "coding_history": "A=PCM,F=48000,W=24,M=mono,T=F8;VERSION=1.10;1:1 0 0 L100 - 30;…"
}
```

### The raw chunks behind them (MEASURED, Python chunk walker)

| | H1 | F8 |
|---|---|---|
| Chunk order | `bext`(858) `fmt `(16) `PAD `(31850) `data` | `bext`(1114) `iXML`(5226) `fmt `(16) `PAD `(124664) `data` |
| bext Description | empty | `SPEED=…\r\nTAKE=…\r\nSCENE=…` key=value lines |
| bext Originator | `ZOOM Handy Recorder H1` | `ZOOM F8` |
| OriginatorReference | empty | empty |
| OriginationDate | `2010-01-01` (hyphens) | `2019-02-13` |
| OriginationTime | `00:00:04` etc. (colons) | `22:40:18` |
| TimeReference | 384000 at 96 kHz = **4 s** = 00:00:04. **Identical to OriginationTime** in all three files (436224000/96000 = 4544 s = 01:15:44; 509088000/96000 = 01:28:23). | 3917280000 at 48 kHz = 81610 s = **22:40:10**. That is **8 s earlier than** OriginationTime 22:40:18. |
| bext Version | 0 | 1 (UMID all zero, so ffmpeg emits no `umid` key) |
| CodingHistory | `A=PCM,F=96000,W=24,M=stereo,T=ZOOM Handy Recorder H1` | `A=PCM,F=48000,W=24,M=mono,T=F8;VERSION=1.10;…` |
| iXML | none | present. `<FILE_UID>ZOOM F8    201902132240180180003</FILE_UID>` and `<FAMILY_UID>` embed the RTC start `20190213224018`. `<SPEED><TIMESTAMP_SAMPLES_SINCE_MIDNIGHT_LO>3917280000` repeats TimeReference. |

Two readings follow (INFERRED from the measurements above):
- **H-series:** TimeReference is just the RTC time-of-day at start × sample rate, so it carries nothing that OriginationTime lacks.
- **F-series:** TimeReference is the **timecode** generator, which can drift from the RTC or be jammed to anything. The F6 manual documents RTC→timecode jamming only in "Int RTC Run" mode, and notes "Since RTC is less precise than internal timecode, discrepancies will occur" (DOCUMENTED, E_F6.pdf p.~134, https://zoomcorp.com/media/documents/E_F6.pdf). **Use OriginationDate/OriginationTime, not TimeReference, for wall-clock start.**

---

## 1. File naming

Labels are DOCUMENTED unless noted. Manual text is extracted from zoomcorp.com PDFs; URLs are below the table.

| Model | Default name | Date option | Is the date-time the start? |
|---|---|---|---|
| H1n | `ZOOM0001.WAV/MP3` … `ZOOM9999` | `YYMMDD-HHMMSS.WAV/MP3`. The order follows the **Date Format** setting (YYMMDD / MMDDYY / DDMMYY) | **Yes.** "files will be named with the date and time when recording started" (E_H1n.pdf p.56) |
| F1 | `ZOOM0001` … | `YYMMDD-HHMMSS`, following Date Format | **Yes.** "the date and time that the recording started" (E_F1.pdf p.49) |
| H2n | `ZOOM0001(MS).wav` … | `YYMMDD-HHMMSS(MS).wav` | REPORTED, from search-indexed text of https://zoomcorp.com/media/documents/E_H2n_.pdf; the PDF's own text layer is font-garbled. No `SR001` naming was found for the H2n. **`SR001.WAV` is not an H2n default** |
| H2 (original, 2007) | `STE-001.WAV` | — | DOCUMENTED, E_H2.pdf |
| H4n / H4n Pro | Stereo mode `STE-001.wav` / `MONO-001.wav`; 4CH mode `4CH-001M.wav`/`…I.wav` (MTR mode has its own) | `DATE`: `090531-001.wav`. **Date only plus a counter, no time** | Date only. "WAV files recorded in STEREO/4CH/STAMINA mode comply with BWF … and include marks and creation dates" (E_H4n_Pro_REV3.pdf) |
| H5 | project folder `ZOOM0001/` with `ZOOM0001_TrLR.WAV`, `_Tr1`, `_Tr2`, … | `YYMMDD-HHMMSS` (e.g. `140531-163015`) | Yes (manual examples; H6 text states it outright) |
| H6 | folder `ZOOM0001/` with `ZOOM0001_LR.WAV`, `_Tr1`, `_Tr34`, `_BU` (backup), `_VM.MP3` | "Date: YYMMDD-HHMMSS (Example: 130331-123016)" | **Yes.** "The 'Date' format uses the recording starting time" (E_H6.pdf p.86) |
| H8 | project folders `P200101_001`, `M200101_001` (by app) | always `[date]_NNN`, YYMMDD, **date only** | Date only (E_H8_v2.pdf p.~107) |
| H4essential / H6essential / H5studio | **always** `Date_Time` folders and files, e.g. `240101_000000`, with `_TrMic`, `_Tr1`, `_TrLR` suffixes. The date follows Date Format | (no counter option) | **Yes.** "date followed by the hour, minute and second using the set date and time" (E_H4essential_2.pdf p.~68, 87). **A 2 GB continuation file gets a new folder named "the date and time of the moment of continuation"** (p.87) |
| F2, F3 | not obtained (manuals not at a guessable URL) | — | unknown |
| F6 | `Scene001_001.WAV`; poly or `.TAKE` folders with `_Tr1`, `_TL_R` | Scene Name Mode = Date: text example `20190101-001.wav`, figure example `190101_002.MP3`. **Date only plus take number** | Date only (E_F6.pdf p.40, 49) |
| F8 / F8n | `<Scene>-T001.WAV`; DISCRETE `.TAKE` folders with `_Tr1`, `_TrL_R`, `_D` (dual) | Scene Name Mode can be Date | Date only (E_F8n_2.pdf p.50, MEASURED name pattern from the fixture) |
| M2 / M3 | always `<date>_<take number>` | — | **Date only** (E_M2.pdf p.50, E_M3.pdf p.29) |
| PodTrak P4/P8, M4, H1 XLR, H6essential details | not individually verified | — | unknown |

Sources:
- https://zoomcorp.com/media/documents/E_H1n.pdf
- https://zoomcorp.com/media/documents/E_F1.pdf
- https://zoomcorp.com/media/documents/E_H4n_Pro_REV3.pdf
- https://zoomcorp.com/media/documents/E_H5_v2.pdf
- https://zoomcorp.com/media/documents/E_H6.pdf
- https://zoomcorp.com/media/documents/E_H8_v2.pdf
- https://zoomcorp.com/media/documents/E_H4essential_2.pdf
- https://zoomcorp.com/media/documents/E_H6essential_2.pdf
- https://zoomcorp.com/media/documents/E_H5studio.pdf
- https://zoomcorp.com/media/documents/E_F6.pdf
- https://zoomcorp.com/media/documents/E_F8n_2.pdf
- https://zoomcorp.com/media/documents/E_M2.pdf
- https://zoomcorp.com/media/documents/E_M3.pdf
- https://zoomcorp.com/media/documents/E_H2.pdf

Filename hazards:
- **The date order in a filename is user-configurable** (YYMMDD, MMDDYY or DDMMYY; DOCUMENTED H1n, F1, essentials, M2). `240301-…` cannot be disambiguated from the name alone. Cross-check against bext before trusting a filename date.
- **Continuation files after 2 GB carry their own, later, start time** (DOCUMENTED for the essentials). REPORTED for the H1n, where the author calls them "incorrect filenames (and creation dates)": `220314-151617`, `220314-183910`, `220314-220204`, `220315-012458` (https://zachpoff.com/resources/zoom-recorder-technical-details/). The gaps are 3 h 22 m 53 s = 12173 s. 2³¹ bytes ÷ 176 400 B/s (44.1 kHz/16-bit stereo) = 12174 s. So **those names are the true continuation start times, not errors** (INFERRED by arithmetic). The session start is the earliest file of the chain.
- On the H6, the project folder can be date-named while the WAVs inside stay `ZOOM000x_…` (REPORTED, https://dvinfo.net/forum/all-things-audio/525930-zoom-h6-file-name.html).
- Defaults are numeric (`ZOOM0001`, `STE-001`, `Scene…`) on every model except the essentials and M-series. **Most researcher files will not carry a time in their name.**

---

## 2. Metadata

### bext (BWF)
- **Written by H-series and F-series WAVs.** MEASURED for the H1 and F8. DOCUMENTED "BWF" for the H2, H2n, H4n Pro, H5, H6, H8, F1, F6, F8n, M2 and M3 (spec sections of each manual).
- **Originator** strings seen:
  - `ZOOM Handy Recorder H1` (MEASURED)
  - `ZOOM F8` (MEASURED)

  Other models are unverified: no sample was found for the H4n, H5, H6, H1n or F3. Assume a `ZOOM` prefix and a model name, but not a fixed format.
- **CodingHistory** is `A=PCM,F=…,W=…,M=…,T=<model>` with a ZOOM token in `T=`: `T=ZOOM Handy Recorder H1` (MEASURED); the F8 has `T=F8;VERSION=1.10` with **no** "ZOOM" (MEASURED).
- **Description**:
  - F-series and the essentials write `SPEED=`, `TAKE=`, `UBITS=`, `SCENE=`, `TAPE=`, `CIRCLED=`, `TRK…=`, `NOTE=` lines (DOCUMENTED, E_F6.pdf p.188, E_H4essential_2.pdf p.136; MEASURED on the F8).
  - The H1 leaves it empty (MEASURED).
  - The manuals' BEXT tables list only these Description subfields; they **do not mention** OriginationDate/Time, but both are present in both samples.
- **OriginationDate/Time = recording start on the device RTC.** The evidence:
  - The F8's iXML FILE_UID start stamp equals bext 22:40:18 (MEASURED).
  - The H1's TimeReference equals OriginationTime (MEASURED).
  - The manuals equate the RTC date-time with "recording starting time" for filenames (DOCUMENTED).
  - EBU defines both fields as "date/time of creation of the audio sequence" (DOCUMENTED, EBU Tech 3285 v2 p.11, https://tech.ebu.ch/docs/tech/tech3285.pdf).

  That it is the *start* and not the file close is therefore strongly supported, but not proven against a device whose clock is known.
- **Format:** the spec allows any separator in `yyyy?mm?dd` / `hh?mm?ss` (it recommends `-` `_` `:` space or `.`). Zoom uses `-` and `:` (MEASURED). **There is no timezone field** in bext (DOCUMENTED, Tech 3285).

### iXML
- **F-series write it** (MEASURED F8; DOCUMENTED F6/F8n with tables of written tags, including `TIMESTAMP_SAMPLES_SINCE_MIDNIGHT_HI/LO`, `TIMESTAMP_SAMPLE_RATE`, `FILE_UID`). No iXML tag carries a date as such. FILE_UID embeds `YYYYMMDDHHMMSS` on the F8 (MEASURED; the format is Zoom's own, not in the spec).
- **H4essential, H6essential, H5studio: optional**, "Metadata (iXML)" Off/Write (DOCUMENTED). The default was not stated in the extracted text. **M2: "BWF and iXML formats supported"** (DOCUMENTED).
- **H1: none** (MEASURED). No iXML mentions in the H1n, H5, H6 or H8 manuals (DOCUMENTED by absence).
- **ffmpeg does not parse iXML at all.** There is no `iXML` case in `wavdec.c` (MEASURED by grep of FFmpeg master). Reading it means walking the RIFF chunks yourself.

### Timezone setting
- **None.** No manual of the 15 obtained mentions time zone, UTC, GMT or daylight/summer time (MEASURED: grep over all extracted manual text). The clock is a bare local wall clock with **no offset recorded anywhere** in the file.
- The M3 sets its clock from the connected computer (DOCUMENTED, E_M3.pdf p.38), presumably the computer's local time.

### Unset or reset clock
- **H1: date `2010-01-01`, time counting up from power-on** (MEASURED: `00:00:04`, `01:15:44`, `01:28:23` across a session).
- REPORTED: an H4 produced files dated 1/1/2000 00:00:00 (secondary search summary; the primary source was not retrieved, so treat this as weak).
- How long each model keeps its clock without power (all DOCUMENTED unless marked):
  - H4n Pro: loses the clock after **more than 3 minutes** without power, and the manual tells users to reset it "after every battery change" (E_H4n_Pro_REV3.pdf p.26).
  - H2: loses it after about **1–2 minutes** (E_H2.pdf).
  - H1n: loses it after **15–20 minutes** (REPORTED, zachpoff.com above).
  - F6: has a rechargeable backup cell ("The date and time reset frequently → turn the power on to charge the built-in rechargeable battery", E_F6.pdf p.187).
  - Every model forces a Set Date/Time screen on the next boot (DOCUMENTED), but a user can dismiss it or set it wrongly.
- Consequence: a clock-reset Zoom writes a plausible-looking *time* on a fixed sentinel *date*. The time-of-day is "time since power-on", not wall clock.

### MP3 mode
- **F1, F6 (and the F-series generally): ID3v1 only** (DOCUMENTED, E_F6.pdf p.66, 191; E_F1.pdf spec). The F6 maps timecode → Artist `TC=[HH:MM:SS:FF]`, scene/take → Title `SC=… TK=…`, frame rate and length → Album `FR=… D=…`. **No date field is documented.** ID3v1 has only a 4-character Year, and Zoom does not say it fills it.
- H-series MP3: no tag documentation found. Assume **no date in the file**. The only sources are the filename (if date-named) and the FAT timestamp. INFERRED; no sample was obtained.

---

## 3. What ffprobe shows (MEASURED + source)

FFmpeg's wav demuxer (`libavformat/wavdec.c`, `wav_parse_bext_tag`, master as of 11 Oct 2026, https://github.com/FFmpeg/FFmpeg/blob/master/libavformat/wavdec.c) reads bext into these **internal** keys:

`description`, `originator`, `originator_reference`, `origination_date`, `origination_time`, `time_reference` (decimal sample count), `umid` (only if bext version ≥ 1 and non-zero), `coding_history` (if the chunk is > 602 bytes). Empty strings are skipped.

Then `wav_read_header` calls `ff_metadata_conv_ctx(s, NULL, wav_metadata_conv)`, which **renames** four of them to generic keys:

```c
static const AVMetadataConv wav_metadata_conv[] = {
    { "description",      "comment"       },
    { "originator",       "encoded_by"    },
    { "origination_date", "date"          },
    { "origination_time", "creation_time" },
};
```

So the **ffprobe `format.tags` keys actually seen are:**

| bext field | ffprobe key | Example (MEASURED) |
|---|---|---|
| Description | `comment` | `SPEED=25.000ND\r\nTAKE=001…` |
| Originator | `encoded_by` | `ZOOM F8` / `ZOOM Handy Recorder H1` |
| OriginatorReference | `originator_reference` (kept; absent when empty) | absent in both |
| OriginationDate | **`date`** | `2019-02-13` |
| OriginationTime | **`creation_time`** | `22:40:18`. **A bare time, not ISO-8601** |
| TimeReference | `time_reference` | `3917280000` |
| UMID | `umid` | absent (zero) |
| CodingHistory | `coding_history` | `A=PCM,F=48000,…` |

The belief in the brief is **half right**: `time_reference` and `coding_history` are as expected, but there is **no `origination_date`, `origination_time` or `originator` key** in ffprobe output. They surface as `date`, `creation_time` and `encoded_by`.

Gotchas:
- `creation_time` on a WAV is `HH:MM:SS` only. Generic code that does `datetime.fromisoformat(tags["creation_time"])` (correct for MP4/MOV, which give `2019-02-13T22:40:18.000000Z`) will fail or produce a wrong date. You must combine `date` + `creation_time`.
- A `LIST/INFO` `ICRD` chunk also maps to `date` via `ff_riff_info_conv`. A file with both could carry two `date` values (INFERRED from the conv tables; not observed in the samples).
- `encoded_by` is ambiguous for non-BWF files: an INFO `ITCH`/`ISFT`, or an ID3 `TENC`, can map there too. Recognise Zoom from **`encoded_by` together with `time_reference`/`coding_history`**, not from `encoded_by` alone.

---

## 4. FAT timestamps on the card

- **Not measured.** No device was available, and the downloaded files' timestamps are git/HTTP artefacts.
- FAT stores a create time (10 ms) and a modify time (2 s), both **local time with no zone**. Typical embedded FAT stacks (e.g. FatFs) stamp the **create time when the file is opened** and the **modify time on sync/close**. On that basis: birth ≈ start, mtime ≈ end (INFERRED; Zoom's firmware stack is not public).
- The H4n Pro's file-info screen describes DATE as "Recorded date of file (or modification date when created by a computer or other device)" (DOCUMENTED, E_H4n_Pro_REV3.pdf). That suggests the device reads its own directory timestamp back, but it does not say which one.
- Practical caveats (INFERRED):
  - macOS's msdos driver interprets FAT local times in the Mac's current zone.
  - Copying off the card (`cp`, AirDrop, cloud sync, Zoom's own export) usually rewrites birthtime and often mtime.
  - With an unset clock, both FAT stamps sit on the sentinel date.

  So the FS date is the **weakest** source. Use it only when bext and filename are absent, and only if it is not a sentinel.

---

## 5. Recommended rule

**Recognise a Zoom-recorder file.** All of the following:
1. Container is WAV/RF64.
2. ffprobe `format.tags.encoded_by` (bext Originator) starts with `ZOOM` (case-insensitive), **or** `coding_history` contains `T=ZOOM`, **or** `coding_history` matches `T=F\d` / `T=H\d` / `T=M\d` / `T=P\d`, **or** an iXML `FILE_UID` starts `ZOOM `.
3. Supporting signals: a `time_reference` key is present; a `PAD ` chunk; filename `ZOOM\d{4}(_\w+)?\.WAV`, `STE-\d{3}`, `\d{6}[-_]\d{6}` or `<scene>-T\d{3}`.

**Turn the fields into a start instant.**
1. `start_local = parse(date) + parse(creation_time)`. Accept any single separator, since the spec allows `-` `_` `:` space or `.`. This is a **naive local wall-clock** time, so tag it as such and never stamp UTC on it.
2. **Do not use `time_reference` as wall clock.** On F-series it is timecode, measured 8 s off the RTC. On H-series it duplicates `creation_time`. It can serve as a consistency check only: if `round(time_reference / sample_rate) mod 86400` is within a few seconds of `creation_time`, the device is in RTC-like mode.
3. **Unset-clock detection.** Treat the date as unknown (but keep the time-of-day only as "elapsed since power-on", i.e. don't show it) when any of these hold:
   - date ∈ {`2010-01-01`, `2000-01-01`} or any `YYYY-01-01` with a time under a few hours;
   - the date is before the model's release (H1 2010, H4n 2009, H5 2014, H6 2013, F8 2015, H1n 2018, F6 2019, essentials 2024);
   - the date is in the future relative to the file's arrival.
4. **Timezone.** There is none in the file. Resolve the naive local time against the **researcher's/project's zone** (or the importing machine's zone as a labelled default), and show it as local time. Say "recorder clock, no timezone" rather than inventing an offset. A recorder that was not moved to summer time will be an hour off, and nothing in the file can reveal that.
5. **Precedence:**
   1. bext `date`+`creation_time` (sane);
   2. iXML `FILE_UID` 14-digit stamp (F-series);
   3. date-time filename `YYMMDD-HHMMSS`. Only if the bext date agrees with the name under one of the three date orders. If bext is absent, take the order from context or flag it as ambiguous;
   4. date-only names (`090531-001`, `20190101-001`, M2/M3/H8/F-series Date mode), which give the **day only**;
   5. FAT birthtime, not sentinel, explicitly labelled low confidence.
6. **Split recordings.** Files over 2 GB continue in a new file (`-0001`/`_01` suffix, `_0002` long-file number, or a new date-time folder on the essentials). Each file's own bext/name is *that file's* start. The interview start is the minimum across the chain.
7. **Multitrack siblings** (`_Tr1`, `_TrLR`, `_D`, MULTI) share one start (MEASURED: identical bext across all three F8 files). Dedupe them, don't treat them as separate sessions.
8. **MP3 from Zoom:** there is no date in the file (F-series ID3v1 carries TC/scene only). Use the filename or the FS date.

---

## Open questions
- Exact Originator/CodingHistory strings for the H1n, H4n Pro, H5, H6, F3 and PodTrak. Bring one real file per model.
- Unset-clock sentinel dates for the newer models (the H1n and essentials).
- The FAT create vs modify behaviour, on a real card.
- Whether a 2 GB continuation file's bext carries the continuation start (expected) or the session start.
