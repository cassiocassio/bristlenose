# The Hello World Study — An End-to-End Architecture Walkthrough

> **What this document is:** A trace of one tiny study through every layer of Bristlenose — from raw interview recordings all the way to a clickable quote in your browser and back again when you tag it. Every Python function, every LLM prompt, every database row, every React component, every CSS token.
>
> **Who it's for:** Two audiences. If you're a researcher who wants to understand *why* Bristlenose does what it does, read the plain-language explanations. If you're an engineer who wants to understand *how*, read the code fragments. Both are interleaved throughout.

---

## The Study

You're running a two-session user study. The question: *"How would you write a Hello World program in your favourite programming language?"*

| Session | Platform | Participant | Language | Duration |
|---------|----------|-------------|----------|----------|
| s1 | Zoom | Alice (p1) | Python | ~1 min |
| s2 | Teams | Bob (p2) | Rust | ~1 min |

Each participant reads out their code and explains why they love the language — the syntax, the philosophy, what it feels like to write. You record both calls. Now you want to analyse them.

Your input folder looks like this:

```
hello-world-study/
├── GMT20260221-140000_Recording.mp4          # Zoom export (Alice)
├── GMT20260221-140000_Recording.vtt          # Zoom auto-caption
└── Hello World Study-20260221_150000.mp4     # Teams export (Bob)
```

You run:

```bash
bristlenose hello-world-study/
```

This single command triggers a 12-stage pipeline, 4 LLM calls, a SQLite import, a FastAPI server, and a React application. Here is everything that happens.

---

## Part 1: The Command Line

### 1.1 CLI Dispatch

**What happens:** Bristlenose figures out you want to run the full pipeline.

**Why:** The CLI supports multiple commands (`run`, `serve`, `render`, `analyze`, `doctor`). But the most common thing people do is point it at a folder. So if the first argument is a directory that exists, `run` is injected automatically.

```python
# bristlenose/cli.py — auto-inject 'run' if first arg is a directory
def _maybe_inject_run(args: list[str]) -> list[str]:
    if args and Path(args[0]).is_dir() and args[0] not in _KNOWN_COMMANDS:
        return ["run"] + args
    return args
```

`bristlenose hello-world-study/` becomes `bristlenose run hello-world-study/`.

### 1.2 Settings Resolution

**What happens:** Configuration is assembled from four sources, last wins.

**Why:** Researchers shouldn't have to pass 20 flags every time. Sane defaults cover 90% of cases. A `.env` file covers the rest. CLI flags override everything for one-off tweaks.

```
Defaults (hardcoded) → .env file → Environment variables → CLI flags
```

The key settings for our study:

```python
# bristlenose/config.py (simplified)
class BristlenoseSettings(BaseModel):
    llm_provider: str = "anthropic"          # Which LLM to use
    llm_model: str = "claude-sonnet-4-20250514"
    anthropic_api_key: str = ""              # From .env or ANTHROPIC_API_KEY
    llm_concurrency: int = 3                 # Max parallel LLM calls
    llm_max_tokens: int = 32768              # Output token ceiling
    pii_enabled: bool = False                # PII redaction off by default
    transcription_backend: str = "auto"      # MLX on Apple Silicon, faster-whisper otherwise
```

### 1.3 Pipeline Instantiation

**What happens:** The `Pipeline` object is created with settings, a timing estimator, and an event callback.

```python
# bristlenose/pipeline.py
class Pipeline:
    def __init__(
        self,
        settings: BristlenoseSettings,
        on_event: object = None,       # For future progress-bar UI
        estimator: object = None,      # Welford timing estimator
    ):
        self.settings = settings
        self._console = Console(width=min(80, Console().width))
```

**Why `Console(width=min(80, ...))`?** The `Console()` inside `min()` is a throwaway Rich instance that auto-detects the real terminal width. The outer `Console(width=...)` is the one that formats output. This caps line width at 80 characters for clean, Cargo-style output:

```
Bristlenose v0.10.2 · Claude · Apple Silicon

2 sessions in hello-world-study/

 ✓ Ingested 2 sessions (2 video, 1 vtt)         0.1s
```

---

## Part 2: Ingestion (Stage 1)

### 2.1 File Discovery

**What happens:** Bristlenose scans the input folder, classifies every file by type, and groups them into sessions.

**Why:** Interview recordings come in many formats from many platforms. A single Zoom call might produce an `.mp4`, a `.vtt` caption file, and an `.m4a` audio-only backup — all with slightly different names. Bristlenose needs to figure out that these all belong to the same interview session.

```python
# bristlenose/stages/ingest.py
def ingest(input_dir: Path) -> list[InputSession]:
    """Discover files, classify types, group into sessions."""
```

**File classification** maps extensions to types:

```python
_EXT_MAP = {
    ".mp4": FileType.VIDEO,
    ".mov": FileType.VIDEO,
    ".webm": FileType.VIDEO,
    ".mp3": FileType.AUDIO,
    ".wav": FileType.AUDIO,
    ".m4a": FileType.AUDIO,
    ".vtt": FileType.SUBTITLE_VTT,
    ".srt": FileType.SUBTITLE_SRT,
    ".docx": FileType.DOCX,
}
```

For our Hello World study, the scan finds:

| File | Type | Platform hint |
|------|------|---------------|
| `GMT20260221-140000_Recording.mp4` | VIDEO | Zoom (GMT prefix) |
| `GMT20260221-140000_Recording.vtt` | SUBTITLE_VTT | Zoom caption |
| `Hello World Study-20260221_150000.mp4` | VIDEO | Teams (date suffix) |

### 2.2 Session Grouping

**What happens:** Files are grouped into sessions using a two-pass heuristic.

**Why:** Different video platforms name files differently. Zoom uses `GMT` timestamps. Teams uses `Title-YYYYMMDD_HHMMSS`. Google Meet uses `Name (date)`. The grouper normalises these patterns so files from the same call end up together.

**Pass 1 — Zoom folder detection:**
```python
# If files live in a Zoom-style folder (YYYY-MM-DD HH.MM.SS ...),
# everything in that folder is one session.
```

**Pass 2 — Stem normalisation:**
```python
def _normalise_stem(stem: str) -> str:
    """Strip platform-specific suffixes to find the 'core' name."""
    # Zoom: "GMT20260221-140000_Recording" → "recording"
    # Teams: "Hello World Study-20260221_150000" → "hello world study"
    # The details don't matter — what matters is that files from the
    # same call normalise to the same string.
```

**Important:** `_normalise_stem()` expects a **lowercased** stem. Callers must `.lower()` before passing.

For our study, the grouper produces:

```python
[
    InputSession(
        session_id="s1",              # First by creation date
        participant_id="p1",          # Provisional — reassigned later
        files=[
            InputFile(path="GMT...mp4", file_type=VIDEO, duration=62.5),
            InputFile(path="GMT...vtt", file_type=SUBTITLE_VTT),
        ],
    ),
    InputSession(
        session_id="s2",
        participant_id="p2",
        files=[
            InputFile(path="Hello World...mp4", file_type=VIDEO, duration=58.3),
        ],
    ),
]
```

**Key data model:**

```python
# bristlenose/models.py
class InputFile(BaseModel):
    path: Path
    file_type: FileType
    creation_date: datetime | None = None
    duration_seconds: float | None = None

class InputSession(BaseModel):
    session_id: str              # "s1", "s2", ...
    participant_id: str          # "p1", "p2", ... (provisional)
    files: list[InputFile]
    audio_path: Path | None = None   # Set by Stage 2
```

**Participant IDs are assigned by creation date** — the earliest session gets `p1`. This is provisional. After speaker identification (Stage 5b), participants get permanent speaker codes (`p1`, `p2`) based on their actual role in the conversation.

---

## Part 3: Audio & Transcription (Stages 2–6)

### 3.1 Extract Audio (Stage 2)

**What happens:** FFmpeg extracts audio tracks from video files.

**Why:** Speech recognition models (Whisper) work on audio, not video. We need to strip the audio track. This is a fast, local operation — no cloud, no API keys.

```python
# bristlenose/stages/extract_audio.py
async def extract_audio_for_sessions(
    sessions: list[InputSession], temp_dir: Path, concurrency: int = 4
) -> list[InputSession]:
```

For session s1 (Zoom), we already have a `.vtt` caption file, so Whisper won't be called — but audio is still extracted for the media player. For session s2 (Teams), there's no caption file, so audio extraction is essential.

```bash
# What FFmpeg actually runs (simplified):
ffmpeg -hwaccel videotoolbox -i "Hello World Study-20260221_150000.mp4" \
       -vn -acodec pcm_s16le -ar 16000 \
       ".bristlenose/temp/s2_extracted.wav"
```

**`-hwaccel videotoolbox`** uses Apple's hardware video decoder on macOS. The audio is downsampled to 16kHz mono WAV — that's what Whisper expects.

**Concurrency:** Up to 4 extractions run in parallel via `asyncio.Semaphore(4)`. The blocking `subprocess.run()` call is wrapped in `asyncio.to_thread()` so it doesn't block the event loop.

### 3.2 Transcription (Stages 3–5a)

**What happens:** Each session gets a word-level transcript with timestamps.

**Why:** This is the foundation of everything. Without a transcript, there are no quotes to extract. Bristlenose supports two paths:

1. **Platform transcript** (s1): Zoom already generated a `.vtt` file. Parse it directly — faster, free, no model needed.
2. **Whisper transcription** (s2): No existing transcript. Run a local speech-to-text model.

#### Path 1: VTT Parsing (Session s1)

```python
# bristlenose/stages/parse_subtitles.py
def parse_vtt(vtt_path: Path) -> list[TranscriptSegment]:
    """Parse WebVTT caption file into segments."""
```

A VTT file looks like this:

```
WEBVTT

00:00:05.000 --> 00:00:12.500
So my favourite language is Python.
I'd write hello world like this: print open paren quote hello world quote close paren.

00:00:13.000 --> 00:00:22.000
What I love about it is the simplicity.
There's no boilerplate, no main function, no semicolons.
```

Each VTT cue becomes a `TranscriptSegment`:

```python
TranscriptSegment(
    start_time=5.0,
    end_time=12.5,
    text="So my favourite language is Python. I'd write hello world like this...",
    speaker_label="Speaker A",    # VTT doesn't identify speakers
    source="vtt",
)
```

#### Path 2: Whisper Transcription (Session s2)

```python
# bristlenose/stages/transcribe.py
def transcribe_sessions(
    sessions: list[InputSession], settings: BristlenoseSettings
) -> dict[str, list[TranscriptSegment]]:
```

**Backend selection** is hardware-adaptive:

```python
# bristlenose/utils/hardware.py
def detect_hardware() -> HardwareInfo:
    # Apple Silicon M1+ → prefer MLX backend (Metal GPU acceleration)
    # NVIDIA GPU → prefer faster-whisper with CUDA
    # CPU only → faster-whisper with INT8 quantization
```

On an M1 Mac, MLX processes our 1-minute Teams recording in about 3 seconds. Whisper produces word-level timestamps with confidence scores:

```python
TranscriptSegment(
    start_time=4.2,
    end_time=9.8,
    text="I would write it in Rust. fn main open brace println...",
    speaker_label="Speaker A",
    words=[
        Word(text="I", start=4.2, end=4.3, confidence=0.98),
        Word(text="would", start=4.3, end=4.5, confidence=0.97),
        # ...
    ],
    source="mlx_whisper",
)
```

### 3.3 Speaker Identification (Stage 5b)

**What happens:** The LLM identifies who is the researcher (moderator) and who is the participant.

**Why:** In every interview, one person asks questions and the other answers them. Bristlenose needs to know which is which so it can:
- Extract quotes only from participants (not the researcher's questions)
- Show researcher questions as context ("When asked about...")
- Assign the right speaker codes (`m1` for moderator, `p1` for participant)

This is the **first LLM call** in the pipeline.

```python
# bristlenose/stages/identify_speakers.py
async def identify_speaker_roles_llm(
    segments: list[TranscriptSegment], llm_client: LLMClient
) -> list[SpeakerInfo]:
```

**Two-pass approach:**

1. **Heuristic pass** (free, instant): Count question marks and researcher phrases ("tell me about", "can you describe", "what do you think"). The speaker with the most questions is probably the researcher.

2. **LLM refinement** (costs tokens, more accurate): Send the first ~5 minutes of transcript to Claude and ask it to identify roles and extract names/titles.

The LLM prompt (from `bristlenose/llm/prompts/speaker-identification.md`):

```markdown
## System
You are analysing a user research interview transcript. Identify each speaker's role.

## User
Transcript (first 5 minutes):
{transcript_text}

Identify each speaker as: researcher, participant, or observer.
Extract their name and job title if mentioned.
```

The LLM returns structured output validated against a Pydantic model:

```python
# bristlenose/llm/structured.py
class SpeakerRoleAssignment(BaseModel):
    assignments: list[SpeakerRoleItem]

class SpeakerRoleItem(BaseModel):
    speaker_label: str       # "Speaker A"
    role: str                # "researcher" | "participant" | "observer"
    person_name: str = ""    # "Alice"
    job_title: str = ""      # "Software Engineer"
```

For our Hello World study, the LLM returns:

```json
{
    "assignments": [
        {"speaker_label": "Speaker A", "role": "researcher", "person_name": ""},
        {"speaker_label": "Speaker B", "role": "participant", "person_name": "Alice"}
    ]
}
```

**Speaker codes are then assigned:**

```python
# bristlenose/stages/identify_speakers.py
def assign_speaker_codes(sessions, speaker_infos):
    # RESEARCHER → m1 (moderator, per-session numbering)
    # PARTICIPANT → p1, p2 (global numbering across all sessions)
    # OBSERVER → o1 (per-session)
```

After this stage, our transcript segments have proper codes:

```
[00:05] [m1] How would you write hello world in your favourite language?
[00:12] [p1] So my favourite language is Python...
```

### 3.4 Merge & Write Transcripts (Stage 6)

**What happens:** Raw segments are merged, cleaned, and written to disk as human-readable text files.

**Why:** Two reasons: (1) merging consecutive same-speaker segments removes Whisper's choppy 3-second chunks, and (2) writing transcripts to disk gives researchers a permanent record they can read, share, or import into other tools.

```python
# bristlenose/stages/merge_transcript.py
def merge_transcripts(
    sessions: list[InputSession],
    session_segments: dict[str, list[TranscriptSegment]]
) -> list[FullTranscript]:
```

**Merge rule:** If the same speaker has two consecutive segments less than 2 seconds apart, they're joined into one. This turns:

```
[00:12] [p1] So my favourite language
[00:13] [p1] is Python.
```

Into:

```
[00:12] [p1] So my favourite language is Python.
```

**Segment ordinals** (`segment_index`) are assigned here. These are sequential integers (0, 1, 2...) that let quote sequence detection work later — if quotes come from adjacent segments, they're probably part of the same thought.

**Written output** for session s1:

```
# Transcript: s1
# Source: GMT20260221-140000_Recording.mp4
# Date: 2026-02-21
# Duration: 01:02

[00:05] [m1] How would you write hello world in your favourite language?

[00:12] [p1] So my favourite language is Python. I'd write hello world like this:
print open paren quote hello world quote close paren. What I love about it is
the simplicity. There's no boilerplate, no main function, no semicolons. You
just say what you mean and Python does it. It's like writing pseudocode that
actually runs.
```

**Data model:**

```python
# bristlenose/models.py
class FullTranscript(BaseModel):
    session_id: str                          # "s1"
    participant_id: str                      # "p1"
    source_file: str                         # "GMT20260221-140000_Recording.mp4"
    session_date: datetime
    duration_seconds: float                  # 62.5
    segments: list[TranscriptSegment]        # Merged segments with speaker codes
```

### 3.5 PII Removal (Stage 7) — Skipped

**What happens:** Nothing, for our study. PII removal is off by default.

**Why:** Most user research involves consented participants who signed release forms. Redacting names adds friction and removes context. But when researchers work with sensitive populations (medical, financial), they can enable it with `--redact-pii`, which uses Presidio to detect and replace names, phone numbers, emails, etc.

---

## Part 4: LLM Analysis (Stages 8–11)

This is where Bristlenose becomes more than a transcription tool. Four LLM calls transform raw text into structured research findings.

### 4.1 Topic Segmentation (Stage 8)

**What happens:** The LLM reads each transcript and identifies where the conversation shifts topics.

**Why:** Interviews aren't linear. Researchers jump between topics, participants go on tangents, and the conversation circles back. Topic boundaries let Bristlenose assign quotes to the right section of the report (e.g., "Syntax preferences" vs "Language philosophy").

```python
# bristlenose/stages/topic_segmentation.py
async def segment_topics(
    transcripts: list[PiiCleanTranscript],
    llm_client: LLMClient,
    concurrency: int = 1
) -> list[SessionTopicMap]:
```

**This is the second LLM call.** One call per transcript, running concurrently (bounded by `llm_concurrency`).

The prompt (from `bristlenose/llm/prompts/topic-segmentation.md`):

```markdown
## System
You are analysing a user research interview. Identify where the conversation
shifts to a new topic, screen, or task. Return timecoded boundaries.

## User
{transcript_text}
```

**Inside the LLM client:**

```python
# bristlenose/llm/client.py
async def analyze(
    self,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T],
    max_tokens: int | None = None,
) -> T:
    # 1. Select provider method based on self.provider
    # 2. Convert response_model to JSON schema
    # 3. Make API call with structured output
    # 4. Validate response against Pydantic model
    # 5. Record token usage
    return validated_result
```

**For Claude (Anthropic), structured output uses tool use:**

```python
# bristlenose/llm/client.py — _analyze_anthropic()
response = await self._anthropic_client.messages.create(
    model=self.settings.llm_model,
    max_tokens=max_tokens or self.settings.llm_max_tokens,
    system=system_prompt,
    messages=[{"role": "user", "content": user_prompt}],
    tools=[{
        "name": "respond",
        "description": "Return structured analysis",
        "input_schema": response_model.model_json_schema(),
    }],
    tool_choice={"type": "tool", "name": "respond"},  # Force structured output
    timeout=600.0,  # Never remove — SDK rejects large max_tokens without this
)
```

The LLM returns for session s1 (Alice):

```python
TopicSegmentationResult(boundaries=[
    TopicBoundaryItem(
        timecode="00:05",
        topic_label="Hello World in Python",
        transition_type="topic_shift",
        confidence=0.95,
    ),
    TopicBoundaryItem(
        timecode="00:25",
        topic_label="Language philosophy — simplicity",
        transition_type="topic_shift",
        confidence=0.88,
    ),
])
```

These are converted to domain models:

```python
# bristlenose/models.py
class SessionTopicMap(BaseModel):
    session_id: str                          # "s1"
    participant_id: str                      # "p1"
    boundaries: list[TopicBoundary]

class TopicBoundary(BaseModel):
    timecode_seconds: float                  # 5.0
    topic_label: str                         # "Hello World in Python"
    transition_type: TransitionType          # TOPIC_SHIFT
    confidence: float                        # 0.95
```

**Caching:** The result is written to `.bristlenose/intermediate/topic_boundaries.json`. If the pipeline crashes after this stage, it won't re-run on the next attempt.

### 4.2 Quote Extraction (Stage 9)

**What happens:** The LLM reads each transcript + topic boundaries and extracts the most meaningful participant quotes.

**Why:** This is the core value of Bristlenose. A 1-hour interview has ~8,000 words. A good research report has ~20-30 quotes. The LLM selects the quotes that best represent what participants said, tags each with sentiment, and links them to topics.

```python
# bristlenose/stages/quote_extraction.py
async def extract_quotes(
    transcripts: list[PiiCleanTranscript],
    topic_maps: list[SessionTopicMap],
    llm_client: LLMClient,
    min_quote_words: int = 5,
    concurrency: int = 1
) -> list[ExtractedQuote]:
```

**This is the third LLM call** — the most token-intensive. One call per transcript.

The prompt sends the full transcript plus topic boundaries:

```markdown
## System
You are a user research analyst extracting verbatim quotes from interview transcripts.

For each quote:
- Extract the EXACT words the participant used
- Classify as "screen_specific" (about a particular feature/screen) or "general_context" (broader observation)
- Tag sentiment: frustration, confusion, doubt, surprise, satisfaction, delight, or confidence
- Rate intensity: 1 (mild), 2 (moderate), 3 (strong)
- Note the researcher's question that prompted it

## User
Topic boundaries:
{topic_boundaries}

Transcript:
{transcript_text}
```

For Alice (s1), the LLM might extract:

```python
ExtractedQuote(
    session_id="s1",
    participant_id="p1",
    start_timecode=12.0,
    end_timecode=22.0,
    text="What I love about Python is the simplicity. There\u2019s no boilerplate, "
         "no main function, no semicolons. You just say what you mean and Python does it.",
    verbatim_excerpt="What I love about it is the simplicity...",
    topic_label="Language philosophy — simplicity",
    quote_type=QuoteType.GENERAL_CONTEXT,       # Not about a specific screen
    sentiment=Sentiment.DELIGHT,                 # She loves it
    intensity=2,                                 # Moderate enthusiasm
    researcher_context="When asked about their favourite language",
    segment_index=3,                             # 4th segment in transcript
)
```

For Bob (s2), something different:

```python
ExtractedQuote(
    session_id="s2",
    participant_id="p2",
    start_timecode=15.0,
    end_timecode=28.0,
    text="The compiler catches everything. If it compiles, it works. "
         "That\u2019s the deal with Rust \u2014 you pay upfront with strict syntax, "
         "but you never get a runtime surprise.",
    verbatim_excerpt="The compiler catches everything...",
    topic_label="Language philosophy — safety",
    quote_type=QuoteType.GENERAL_CONTEXT,
    sentiment=Sentiment.CONFIDENCE,              # He trusts the compiler
    intensity=3,                                 # Strong conviction
    researcher_context="When explaining Rust's type system",
    segment_index=4,
)
```

**The seven sentiments** come from established UX research literature (documented in `docs/design-research-methodology.md`):

| Sentiment | Valence | Example |
|-----------|---------|---------|
| Frustration | Negative | "This is so annoying" |
| Confusion | Negative | "I don't understand why..." |
| Doubt | Negative | "I'm not sure this is right" |
| Surprise | Neutral | "Oh! I didn't expect that" |
| Satisfaction | Positive | "Yeah, that works well" |
| Delight | Positive | "I love this!" |
| Confidence | Positive | "I know exactly what to do" |

**Data model:**

```python
# bristlenose/models.py
class ExtractedQuote(BaseModel):
    session_id: str
    participant_id: str
    start_timecode: float
    end_timecode: float
    text: str                        # Cleaned (filler words removed, smart quotes)
    verbatim_excerpt: str            # Exact original for verification
    topic_label: str
    quote_type: QuoteType            # SCREEN_SPECIFIC or GENERAL_CONTEXT
    sentiment: Sentiment | None
    intensity: int                   # 1, 2, or 3
    researcher_context: str | None
    segment_index: int               # For quote sequence detection
```

**Quote ID format:** Each quote gets a DOM ID of `q-{participant_id}-{int(start_timecode)}`. For Alice's quote: `q-p1-12`. This ID is stable across re-renders and is used everywhere — localStorage, API calls, React state.

### 4.3 Quote Clustering (Stage 10) & Thematic Grouping (Stage 11)

**What happens:** The LLM organises quotes into sections (by screen/feature) and themes (by cross-cutting pattern).

**Why:** A flat list of 30 quotes is hard to read. Researchers need structure — "here are the 5 quotes about the dashboard" and "here are the 4 quotes about trust issues." The LLM creates this structure automatically.

**These two stages run concurrently** — they're independent:

```python
# bristlenose/pipeline.py
screen_clusters, theme_groups = await asyncio.gather(
    cluster_by_screen(screen_quotes, llm_client),   # Stage 10
    group_by_theme(context_quotes, llm_client),      # Stage 11
)
```

**Quote exclusivity is enforced at three levels:**

1. **Type separation** (Stage 9): Each quote is tagged `SCREEN_SPECIFIC` or `GENERAL_CONTEXT`
2. **Clustering** (Stage 10): Only `SCREEN_SPECIFIC` quotes → screen clusters
3. **Theming** (Stage 11): Only `GENERAL_CONTEXT` quotes → theme groups

**Every quote appears in exactly one section of the report.** This matches researcher expectations — when they hand the report to a stakeholder, each quote appears once.

For our tiny study, clustering might produce:

```python
ScreenCluster(
    screen_label="Hello World Code",
    description="Participants demonstrating their preferred Hello World implementations",
    display_order=1,
    quotes=[alice_code_quote, bob_code_quote],  # SCREEN_SPECIFIC quotes only
)
```

And theming might produce:

```python
ThemeGroup(
    theme_label="Language philosophy",
    description="Participants explaining what they value most about their chosen language",
    quotes=[alice_simplicity_quote, bob_safety_quote],  # GENERAL_CONTEXT quotes only
)
```

**Token efficiency:** The LLM receives quotes as compact JSON with indices, not full objects:

```python
# bristlenose/stages/quote_clustering.py
quotes_json = json.dumps(quotes_for_llm, ensure_ascii=False, separators=(",", ":"))
# separators=(",",":") saves ~15% tokens by removing whitespace
```

The LLM returns **indices** into the quote array:

```json
{
    "clusters": [
        {
            "screen_label": "Hello World Code",
            "description": "...",
            "display_order": 1,
            "quote_indices": [0, 3]
        }
    ]
}
```

These indices are resolved back to full quote objects in Python. This minimises token usage — the LLM only needs to output small integers, not full quote text.

---

## Part 5: The Intermediate Layer

### 5.1 JSON Persistence

**What happens:** After each LLM stage completes, results are written to JSON files in the `.bristlenose/intermediate/` directory.

**Why:** LLM calls are expensive (they cost money and take time). If the pipeline crashes at Stage 11, you don't want to re-run Stages 8-10. The intermediate JSON files act as checkpoints.

```
hello-world-study/bristlenose-output/.bristlenose/
├── pipeline-manifest.json              # Stage completion tracking
├── intermediate/
│   ├── topic_boundaries.json           # Stage 8 output
│   ├── extracted_quotes.json           # Stage 9 output
│   ├── screen_clusters.json            # Stage 10 output
│   └── theme_groups.json               # Stage 11 output
├── speaker-info/
│   ├── s1.json                         # Stage 5b output (per-session)
│   └── s2.json
└── temp/
    └── s2_extracted.wav                # Stage 2 scratch file
```

### 5.2 The Pipeline Manifest

**What happens:** A JSON file tracks which stages have completed, which sessions within each stage have been processed, and what provider/model was used.

**Why:** This enables three levels of resume:

1. **Stage-level:** "Stage 8 is COMPLETE, skip it entirely"
2. **Session-level:** "Stage 9 completed s1 but not s2 — only process s2"
3. **Full re-run:** "No manifest exists, run everything"

```python
# bristlenose/manifest.py
class PipelineManifest(BaseModel):
    schema_version: int
    project_name: str
    pipeline_version: str
    stages: dict[str, StageRecord]

class StageRecord(BaseModel):
    status: StageStatus      # PENDING, RUNNING, COMPLETE, PARTIAL, FAILED
    sessions: dict[str, SessionRecord] | None   # Per-session tracking

class SessionRecord(BaseModel):
    status: StageStatus
    session_id: str
```

For our study after a successful run:

```json
{
    "schema_version": 1,
    "project_name": "Hello World Study",
    "stages": {
        "topic_segmentation": {
            "status": "COMPLETE",
            "sessions": {
                "s1": {"status": "COMPLETE", "session_id": "s1"},
                "s2": {"status": "COMPLETE", "session_id": "s2"}
            }
        },
        "quote_extraction": {
            "status": "COMPLETE",
            "sessions": {
                "s1": {"status": "COMPLETE", "session_id": "s1"},
                "s2": {"status": "COMPLETE", "session_id": "s2"}
            }
        }
    }
}
```

**Resume logic in the pipeline:**

```python
# bristlenose/pipeline.py — simplified
_prev_manifest = load_manifest(output_dir)

# Stage-level cache check
if _is_stage_cached(_prev_manifest, "topic_segmentation") and tb_path.exists():
    topic_maps = load_from_json(tb_path)       # Skip LLM entirely
    _print_cached_step("Segmented topics", elapsed=0)
else:
    # Per-session resume
    completed_sids = get_completed_session_ids(_prev_manifest, "topic_segmentation")
    remaining = [t for t in transcripts if t.session_id not in completed_sids]
    fresh_maps = await segment_topics(remaining, llm_client)
    topic_maps = cached_maps + fresh_maps
```

### 5.3 Analysis Computation

**What happens:** After clustering and theming, Bristlenose computes signal concentration metrics — pure math, no LLM.

**Why:** Researchers want to know: "Where are the strongest findings?" If 4 out of 5 participants expressed frustration about the checkout flow, that's a strong signal. The analysis page quantifies this with a statistical measure called **concentration ratio** — the observed frequency of a sentiment in a section divided by its expected frequency if quotes were distributed randomly.

```python
# bristlenose/pipeline.py
analysis = _compute_analysis(screen_clusters, theme_groups, all_quotes, n_participants)

# bristlenose/analysis/metrics.py
def concentration_ratio(cell_count, row_total, col_total, grand_total):
    """How overrepresented is this sentiment in this section?

    ratio > 2.0 → strong signal (twice as much frustration here as expected)
    ratio > 1.5 → moderate signal
    ratio > 1.0 → mild signal
    ratio < 1.0 → underrepresented
    """
    observed = cell_count / row_total if row_total else 0
    expected = col_total / grand_total if grand_total else 0
    return observed / expected if expected else 0
```

For our study, if Alice expressed delight about Python's simplicity and Bob expressed confidence about Rust's safety — and there's only one section — the concentration ratios would both be 1.0 (exactly expected). But with a real study of 10+ sessions, patterns emerge.

---

## Part 6: HTML Rendering (Stage 12)

### 6.1 Report Assembly

**What happens:** All pipeline outputs are assembled into a single interactive HTML file.

**Why:** Researchers need a tangible deliverable they can open, read, share, and present. The HTML report is self-contained — CSS and JS are embedded, no internet connection needed.

```python
# bristlenose/stages/render_html.py
def render_html(
    screen_clusters: list[ScreenCluster],
    theme_groups: list[ThemeGroup],
    sessions: list[InputSession],
    project_name: str,
    output_dir: Path,
    all_quotes: list[ExtractedQuote] | None = None,
    people: PeopleFile | None = None,
    transcripts: list[FullTranscript] | None = None,
    analysis: object | None = None,
    serve_mode: bool = False,
) -> Path:
```

**The report is built as a list of HTML strings:**

```python
parts = []

# 1. Document shell (<!DOCTYPE>, <head>, CSS link)
parts.append(_document_shell_open(title=project_name, css_href="assets/bristlenose-theme.css"))

# 2. Header (logo, project name, participant count, date)
parts.append(_report_header_html(project_name=project_name, ...))

# 3. Global navigation (tabs: Project, Sessions, Quotes, Codebook, Analysis, Settings, About)
parts.append(_jinja_env.get_template("global_nav.html").render())

# 4. Content sections (one per screen cluster)
for cluster in screen_clusters:
    quotes_html = "\n".join(_format_quote_html(q, video_map) for q in cluster.quotes)
    parts.append(section_template.render(label=cluster.screen_label, quotes_html=quotes_html))

# 5. Theme sections
for theme in theme_groups:
    quotes_html = "\n".join(_format_quote_html(q, video_map) for q in theme.quotes)
    parts.append(theme_template.render(label=theme.theme_label, quotes_html=quotes_html))

# 6. Data injection (JavaScript globals)
parts.append(f"<script>var BRISTLENOSE_VIDEO_MAP = {json.dumps(video_map)};</script>")

# 7. Concatenated JS (23 modules in dependency order)
parts.append(f"<script>{_get_report_js()}</script>")

# 8. Write to disk
html_path.write_text("\n".join(parts), encoding="utf-8")
```

### 6.2 Quote Card Rendering

**What happens:** Each quote becomes an interactive HTML blockquote.

```python
# bristlenose/stages/render_html.py
def _format_quote_html(quote: ExtractedQuote, video_map: dict | None = None) -> str:
    quote_id = f"q-{quote.participant_id}-{int(quote.start_timecode)}"
    # ...
    tmpl = _jinja_env.get_template("quote_card.html")
    return tmpl.render(quote_id=quote_id, ...)
```

Alice's Python quote becomes:

```html
<blockquote id="q-p1-12" data-timecode="00:12" data-participant="p1">
    <span class="context">[When asked about their favourite language]</span>
    <div class="quote-row">
        <a class="timecode" data-participant="p1" data-seconds="12" href="#">00:12</a>
        <div class="quote-body">
            <span class="quote-text">"What I love about Python is the simplicity.
            There's no boilerplate, no main function, no semicolons. You just say
            what you mean and Python does it."</span>
            <span class="speaker">— <a href="#" class="speaker-link"
                data-nav-session="s1">p1</a></span>
            <div class="badges">
                <span class="badge badge-ai badge-delight">delight</span>
                <span class="badge badge-add">+</span>
            </div>
        </div>
    </div>
    <button class="hide-btn" title="Hide quote">✕</button>
    <button class="edit-pencil" title="Edit">✎</button>
    <button class="star-btn" title="Star">★</button>
</blockquote>
```

**Every element serves a purpose:**
- `id="q-p1-12"` — stable DOM ID used by localStorage, API calls, React state
- `data-timecode="00:12"` — for video player sync
- `data-participant="p1"` — for participant filtering
- `.badge-delight` — sentiment pill, styled via CSS tokens
- `.badge-add` (+) — click target for user tagging
- `.hide-btn`, `.edit-pencil`, `.star-btn` — researcher interaction buttons

### 6.3 CSS: The Design Token System

**What happens:** 42 CSS files are concatenated in atomic-design order into a single stylesheet.

**Why:** Design tokens ensure visual consistency. Change `--bn-sentiment-delight` in one place, and every delight badge across every page updates. The atomic hierarchy (tokens → atoms → molecules → organisms → templates) means styles compose predictably.

```css
/* bristlenose/theme/tokens.css — the single source of truth */
:root {
    /* Sentiment colours */
    --bn-sentiment-frustration: #ea580c;
    --bn-sentiment-confusion: #dc2626;
    --bn-sentiment-doubt: #a16207;
    --bn-sentiment-surprise: #7c3aed;
    --bn-sentiment-satisfaction: #16a34a;
    --bn-sentiment-delight: #059669;
    --bn-sentiment-confidence: #2563eb;

    /* Codebook colours — OKLCH pentadic palette */
    --bn-ux-1-bg: oklch(94% 0.03 225);      /* Blue set */
    --bn-emo-1-bg: oklch(94% 0.03 4);       /* Red-pink set */
    --bn-task-1-bg: oklch(94% 0.03 155);    /* Green-teal set */

    /* Spacing scale */
    --bn-spacing-xs: 0.25rem;
    --bn-spacing-sm: 0.5rem;
    --bn-spacing-md: 1rem;
    --bn-spacing-lg: 1.5rem;
}
```

**Dark mode is pure CSS — no JavaScript involved:**

```css
/* Uses the native CSS light-dark() function */
@supports (color: light-dark(#000, #fff)) {
    :root {
        --bn-colour-bg: light-dark(#ffffff, #111111);
        --bn-sentiment-delight: light-dark(#059669, #34d399);
    }
}
```

The browser switches automatically based on the user's OS preference. The Settings tab also lets researchers force light/dark via an `<html data-theme="light">` attribute.

**Concatenation order matters:**

```python
_THEME_FILES = [
    "tokens.css",              # Variables first (everything references these)
    "atoms/badge.css",         # Basic building blocks
    "atoms/button.css",
    "molecules/person-badge.css",   # Composed patterns
    "molecules/editable-text.css",
    "organisms/blockquote.css",     # Page sections
    "organisms/toolbar.css",
    "templates/report.css",         # Page layout
    "templates/print.css",          # Print overrides (last to win specificity)
]
```

### 6.4 JavaScript: 23 Modules in Dependency Order

**What happens:** Vanilla JavaScript modules provide all interactivity in the static HTML report.

**Why:** The static report needs to work offline, without a server. All interactivity (search, filtering, editing, starring, hiding) is implemented in vanilla JS that reads/writes localStorage. When serve mode is active, the same actions also sync to the server via fire-and-forget API calls.

**Module load order (simplified dependency chain):**

```
storage.js           → localStorage abstraction
  ↓
badge-utils.js       → DOM element factories
  ↓
modal.js             → Dialog overlay
player.js            → Video/audio sync
  ↓
editing.js           → Inline quote editing
tags.js              → Quote tagging
starred.js           → Star/favourite toggle
hidden.js            → Hide/unhide quotes
  ↓
search.js            → Full-text search
tag-filter.js        → Codebook filter dropdown
csv-export.js        → Export to spreadsheet
  ↓
main.js              → Boot: initializes everything
```

**Example: How starring a quote works**

When the researcher clicks the ★ button on Alice's quote:

```javascript
// bristlenose/theme/js/starred.js
function toggleStar(quoteId) {
    const store = createStore("bristlenose-starred");
    const map = store.get() || {};
    const wasStarred = map[quoteId] || false;
    map[quoteId] = !wasStarred;
    store.set(map);                              // Save to localStorage

    // If we're in serve mode, also sync to the server
    if (window.BRISTLENOSE_API_BASE) {
        fetch(`${window.BRISTLENOSE_API_BASE}/starred`, {
            method: "PUT",
            headers: {"Content-Type": "application/json"},
            body: JSON.stringify(map),
        });
        // Fire-and-forget — no await, no error handling
    }

    // Update DOM
    const blockquote = document.getElementById(quoteId);
    blockquote.classList.toggle("starred");
}
```

This dual-write pattern (localStorage + API) means the report works offline (localStorage) and in serve mode (API sync).

---

## Part 7: The Output

After Stage 12, the complete output directory looks like this:

```
hello-world-study/
├── GMT20260221-140000_Recording.mp4                    # Original input (untouched)
├── GMT20260221-140000_Recording.vtt
├── Hello World Study-20260221_150000.mp4
│
└── bristlenose-output/                                  # Everything Bristlenose created
    ├── bristlenose-hello-world-study-report.html        # Main report
    ├── bristlenose-hello-world-study-report.md          # Markdown companion
    ├── people.yaml                                      # Editable participant registry
    │
    ├── assets/
    │   ├── bristlenose-theme.css                        # 42 concatenated CSS files
    │   ├── bristlenose-logo.png
    │   ├── bristlenose-logo-dark.png
    │   └── bristlenose-player.html                      # Popout video player
    │
    ├── sessions/
    │   ├── transcript_s1.html                           # Alice's transcript page
    │   └── transcript_s2.html                           # Bob's transcript page
    │
    ├── transcripts-raw/
    │   ├── s1.txt                                       # Alice's raw transcript
    │   ├── s1.md
    │   ├── s2.txt                                       # Bob's raw transcript
    │   └── s2.md
    │
    └── .bristlenose/
        ├── pipeline-manifest.json                       # Resume tracking
        ├── bristlenose.log                              # Rotating log file
        ├── intermediate/
        │   ├── topic_boundaries.json
        │   ├── extracted_quotes.json
        │   ├── screen_clusters.json
        │   └── theme_groups.json
        ├── speaker-info/
        │   ├── s1.json
        │   └── s2.json
        └── temp/
            └── s2_extracted.wav
```

**The CLI finishes with a summary:**

```
 ✓ Ingested 2 sessions (2 video, 1 vtt)               0.1s
 ✓ Extracted audio from 1 session                      0.8s
 ✓ Transcribed 2 sessions (2 min, 34 segments)         3.2s
 ✓ Identified speakers                                 1.1s
 ✓ Merged transcripts                                  0.1s
 ✓ Segmented 4 topic boundaries                        2.3s
 ✓ Extracted 8 quotes                                  3.8s
 ✓ Clustered 1 section · Grouped 1 theme               1.2s
 ✓ Rendered report                                     0.2s

  Done in 12.8s · 4 LLM calls · ~$0.02

  → bristlenose-hello-world-study-report.html
```

At this point, the researcher can open the HTML file directly and browse the report. But for the full interactive experience, they'd run `bristlenose serve`.

---

## Part 8: Serve Mode — The Full Stack

### 8.1 Starting the Server

```bash
bristlenose serve hello-world-study/
```

**What happens:** A FastAPI server starts, imports pipeline data into SQLite, injects React components into the HTML report, and serves everything over HTTP.

```python
# bristlenose/server/app.py
def create_app(
    project_dir: Path | None = None,
    dev: bool = False,
) -> FastAPI:
    app = FastAPI(title="Bristlenose")

    # 1. Create SQLite database
    engine = get_engine(db_url)     # SQLite with WAL mode, foreign keys enforced
    init_db(engine)                 # Create 24 tables if they don't exist

    # 2. Import pipeline data
    _import_on_startup(app, project_dir)  # JSON → SQLite (idempotent)

    # 3. Register API routes
    app.include_router(sessions_router, prefix="/api")
    app.include_router(quotes_router, prefix="/api")
    app.include_router(dashboard_router, prefix="/api")
    app.include_router(codebook_router, prefix="/api")
    app.include_router(analysis_router, prefix="/api")
    app.include_router(autocode_router, prefix="/api")
    app.include_router(data_router, prefix="/api")

    # 4. Mount static files
    app.mount("/static", StaticFiles(directory=frontend_dist))  # React bundle
    app.mount("/media", StaticFiles(directory=project_dir))     # Video/audio files
    app.mount("/report", StaticFiles(directory=output_dir))     # HTML report

    # 5. Inject React mount points into HTML
    # (happens at request time via _transform_report_html())

    return app
```

### 8.2 SQLite: The Domain Schema

**What happens:** Pipeline JSON data is imported into a 24-table SQLite database.

**Why:** The static HTML report stores researcher state (stars, tags, edits) in localStorage — which is browser-specific and ephemeral. SQLite provides a persistent, queryable store that survives browser clears, works across devices (via the server), and enables features like the codebook panel and AutoCode that need relational queries.

**The database lives at:**
```
hello-world-study/bristlenose-output/.bristlenose/bristlenose.db
```

**Key tables (simplified):**

```sql
-- Core domain
Project (id, name, slug, input_dir, output_dir)
Session (id, project_id, session_id, session_date, duration_seconds, has_media)
Quote   (id, project_id, session_id, participant_id, start_timecode, end_timecode,
         text, sentiment, intensity, quote_type, topic_label)
ScreenCluster (id, project_id, screen_label, description, display_order)
ThemeGroup    (id, project_id, theme_label, description)

-- Join tables
ClusterQuote (cluster_id, quote_id, assigned_by)    -- "pipeline" or "researcher"
ThemeQuote   (theme_id, quote_id, assigned_by)

-- Researcher state (never overwritten on re-import)
QuoteState   (quote_id, is_hidden, is_starred)
QuoteEdit    (quote_id, edited_text, edited_at)
QuoteTag     (quote_id, tag_definition_id)
HeadingEdit  (project_id, heading_key, edited_text)
DeletedBadge (quote_id, sentiment)                   -- AI badge dismissals

-- Codebook
CodebookGroup (id, name, colour_set, framework_id)
TagDefinition (id, codebook_group_id, name)

-- AutoCode (LLM-assisted tagging)
AutoCodeJob   (id, project_id, framework_id, status, total_quotes, processed_quotes)
ProposedTag   (id, job_id, quote_id, tag_definition_id, confidence, rationale, status)
```

### 8.3 The Import: JSON → SQLite

**What happens:** `import_project()` reads the intermediate JSON files and populates the database.

```python
# bristlenose/server/importer.py
def import_project(db: Session, project_dir: Path) -> None:
    """Idempotent: safe to run on every server startup."""

    # 1. Find or create Project row
    project = db.query(Project).filter_by(slug=slug).first()
    if not project:
        project = Project(name=project_name, slug=slug, ...)
        db.add(project)

    # 2. Import sessions from transcript headers
    for transcript_path in sorted(transcripts_dir.glob("*.txt")):
        # Parse header comments for session metadata
        session = Session(session_id="s1", duration_seconds=62.5, ...)
        db.merge(session)  # Upsert

    # 3. Import quotes from clusters + themes
    for cluster_data in json.loads(clusters_path.read_text()):
        cluster = ScreenCluster(screen_label=cluster_data["screen_label"], ...)
        db.merge(cluster)
        for quote_data in cluster_data["quotes"]:
            quote = Quote(
                session_id=quote_data["session_id"],
                participant_id=quote_data["participant_id"],
                start_timecode=quote_data["start_timecode"],
                text=quote_data["text"],
                sentiment=quote_data["sentiment"],
                last_imported_at=now,  # For stale data cleanup
            )
            db.merge(quote)  # Match by (project_id, session_id, participant_id, start_timecode)
```

**Critical design rule:** Researcher state is **never** overwritten. If a researcher has starred a quote, hidden it, or edited its text, those rows in `QuoteState`/`QuoteEdit` survive re-imports.

### 8.4 React Island Injection

**What happens:** When the browser requests the report HTML, the server replaces static Jinja2 sections with React mount points.

**Why:** This is the migration strategy from static HTML to interactive React. Instead of rewriting everything at once, each section is replaced independently. The static HTML still works if JavaScript fails.

**Step 1 — Render time (Python):** The HTML renderer wraps content in comment markers:

```html
<!-- bn-quote-sections -->
<section class="quote-section">
    <h2>Hello World Code</h2>
    <blockquote id="q-p1-12">...</blockquote>
    <blockquote id="q-p2-15">...</blockquote>
</section>
<!-- /bn-quote-sections -->
```

**Step 2 — Serve time (Python):** Regex replaces the markers with React divs:

```python
# bristlenose/server/app.py
def _transform_report_html(html: str) -> str:
    # Replace static quote sections with React mount point
    html = re.sub(
        r"<!-- bn-quote-sections -->.*?<!-- /bn-quote-sections -->",
        '<div id="bn-quote-sections-root" data-project-id="1"></div>',
        html, flags=re.DOTALL,
    )
    # Inject API base URL for fetch calls
    html = html.replace("</head>",
        '<script>window.BRISTLENOSE_API_BASE = "/api/projects/1";</script>\n</head>')
    # Inject Vite React bundle
    bundle_tags = _extract_bundle_tags()
    html = html.replace("</head>", f"{bundle_tags}\n</head>")
    return html
```

**Step 3 — Browser time (React):** The island mounts:

```typescript
// frontend/src/main.tsx
const sectionsRoot = document.getElementById("bn-quote-sections-root");
if (sectionsRoot) {
    const projectId = sectionsRoot.getAttribute("data-project-id") || "1";
    createRoot(sectionsRoot).render(<QuoteSections projectId={projectId} />);
}
```

**Current React islands:**

| Mount point | Component | What it renders |
|------------|-----------|-----------------|
| `#bn-dashboard-root` | Dashboard | Stats, featured quotes, navigation |
| `#bn-sessions-table-root` | SessionsTable | Session grid with speakers, dates, files |
| `#bn-quote-sections-root` | QuoteSections | Screen-specific findings (quote cards) |
| `#bn-quote-themes-root` | QuoteThemes | Cross-cutting themes (quote cards) |
| `#bn-codebook-root` | CodebookPanel | Tag taxonomy, group management, AutoCode |
| `#bn-analysis-root` | AnalysisPage | Signal cards, heatmaps |
| `#bn-transcript-page-root` | TranscriptPage | Per-session transcript with annotations |

### 8.5 The API Layer

**What happens:** React components fetch data from REST endpoints on mount.

**Why:** React islands are rendered client-side. They need data. The API provides it as JSON, derived from the SQLite database.

**Key endpoints for our study:**

```
GET /api/projects/1/dashboard
    → Stats (2 sessions, 8 quotes, 1 section, 1 theme)
    → Featured quotes (top 3 by intensity × participant diversity)
    → Navigation (section/theme labels for tab switching)

GET /api/projects/1/quotes
    → Sections with quotes:
        [{
            cluster_id: 1,
            screen_label: "Hello World Code",
            quotes: [{
                dom_id: "q-p1-12",
                text: "What I love about Python is the simplicity...",
                sentiment: "delight",
                intensity: 2,
                speaker_name: "Alice",
                is_starred: false,
                is_hidden: false,
                tags: [],
                proposed_tags: [],
            }, ...]
        }]
    → Themes with quotes:
        [{
            theme_id: 1,
            theme_label: "Language philosophy",
            quotes: [...]
        }]

GET /api/projects/1/sessions
    → [{
        session_id: "s1",
        session_date: "2026-02-21",
        duration_seconds: 62.5,
        speakers: [
            {speaker_code: "m1", name: "", role: "researcher"},
            {speaker_code: "p1", name: "Alice", role: "participant"}
        ],
        source_files: [{path: "GMT...mp4", file_type: "video"}],
        sentiment_counts: {delight: 2, confidence: 1},
    }, ...]

GET /api/projects/1/codebook
    → {
        groups: [],              # No codebook imported yet
        all_tag_names: [],
    }
```

**Route handler pattern:**

```python
# bristlenose/server/routes/quotes.py
@router.get("/projects/{project_id}/quotes")
def get_quotes(project_id: int, db: Session = Depends(_get_db)):
    try:
        project = db.query(Project).get(project_id)

        # Build sections
        clusters = db.query(ScreenCluster).filter_by(project_id=project_id).all()
        sections = []
        for cluster in clusters:
            quote_rows = (db.query(Quote)
                .join(ClusterQuote)
                .filter(ClusterQuote.cluster_id == cluster.id)
                .all())
            quotes = [_quote_to_response(q, db) for q in quote_rows]
            sections.append(SectionResponse(
                cluster_id=cluster.id,
                screen_label=cluster.screen_label,
                quotes=quotes,
            ))

        # Build themes (same pattern)
        themes = [...]

        return QuotesListResponse(sections=sections, themes=themes)
    finally:
        db.close()   # Always close — SQLite connection pool is finite
```

---

## Part 9: The Browser — Rendering & Interaction

### 9.1 What the User Sees

When the researcher opens `http://localhost:8150/report/`, they see:

1. **Tab bar** at the top: Project | Sessions | Quotes | Codebook | Analysis | Settings | About
2. **Project tab** (default): Dashboard with summary stats, featured quotes, navigation
3. **Sessions tab**: Table showing both sessions with speakers, dates, durations, sentiment sparklines
4. **Quotes tab**: Section "Hello World Code" with Alice's and Bob's code quotes, then theme "Language philosophy" with their philosophy quotes

### 9.2 React Component Data Flow

When the Quotes tab loads, here's the exact sequence:

```
Browser                          Server
  │                                │
  ├──── GET /api/projects/1/quotes ──────────►
  │                                │ Query SQLite
  │                                │ Build response JSON
  ◄──────────── JSON response ─────┤
  │                                │
  │ QuoteSections renders:         │
  │   sections.map(section =>      │
  │     <QuoteGroup               │
  │       quotes={section.quotes}  │
  │       heading={section.label}  │
  │     />                         │
  │   )                            │
  │                                │
  │ QuoteGroup renders per quote:  │
  │   <QuoteCard                   │
  │     quote={q}                  │
  │     onStar={handleStar}        │
  │     onTag={handleTag}          │
  │   />                           │
```

**The QuoteSections island:**

```typescript
// frontend/src/islands/QuoteSections.tsx (simplified)
export function QuoteSections({ projectId }: { projectId: string }) {
    const [data, setData] = useState<QuotesListResponse | null>(null);

    useEffect(() => {
        getQuotes(projectId).then(setData);
    }, [projectId]);

    if (!data) return <div className="loading">Loading...</div>;

    return (
        <div className="quote-sections">
            {data.sections.map(section => (
                <QuoteGroup
                    key={section.cluster_id}
                    heading={section.screen_label}
                    description={section.description}
                    quotes={section.quotes}
                    groupType="section"
                />
            ))}
        </div>
    );
}
```

**The QuoteCard component (simplified):**

```typescript
// frontend/src/components/QuoteCard.tsx
export function QuoteCard({ quote, onStar, onHide, onTag, onEdit }: QuoteCardProps) {
    return (
        <blockquote
            id={quote.dom_id}
            className={cn("quote-card", { starred: quote.isStarred, "bn-hidden": quote.isHidden })}
        >
            {quote.researcher_context && (
                <span className="context">[{quote.researcher_context}]</span>
            )}
            <div className="quote-row">
                <TimecodeLink
                    participantId={quote.participant_id}
                    seconds={quote.start_timecode}
                />
                <div className="quote-body">
                    <EditableText
                        value={quote.edited_text || quote.text}
                        onCommit={(text) => onEdit(quote.dom_id, text)}
                        trigger="external"
                    />
                    <PersonBadge code={quote.participant_id} name={quote.speaker_name} />
                    <div className="badges">
                        {quote.sentiment && (
                            <Badge
                                text={quote.sentiment}
                                variant="ai"
                                sentiment={quote.sentiment}
                                onDelete={() => onDeleteBadge(quote.dom_id, quote.sentiment)}
                            />
                        )}
                        <TagInput
                            existingTags={quote.tags.map(t => t.name)}
                            onAdd={(name) => onTag(quote.dom_id, name)}
                            vocabulary={allTagNames}
                        />
                    </div>
                </div>
            </div>
            <Toggle icon="star" active={quote.isStarred} onClick={() => onStar(quote.dom_id)} />
            <Toggle icon="hide" active={quote.isHidden} onClick={() => onHide(quote.dom_id)} />
        </blockquote>
    );
}
```

### 9.3 User Interaction: Tagging a Quote

The researcher reads Alice's quote about Python's simplicity and wants to tag it "simplicity." Here's the full round-trip:

**Step 1 — Keystroke:** The researcher clicks the `+` badge on the quote card, types "simplicity", and presses Enter.

```typescript
// frontend/src/components/TagInput.tsx
function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && inputValue.trim()) {
        e.preventDefault();
        onAdd(inputValue.trim());        // Calls parent's onTag handler
        setInputValue("");               // Clear input
    }
}
```

**Step 2 — React state update:** QuoteGroup updates its local state map:

```typescript
// frontend/src/islands/QuoteGroup.tsx
function handleTag(domId: string, tagName: string) {
    setStateMap(prev => {
        const quote = prev[domId];
        const newTags = [...quote.tags, { name: tagName, codebook_group: "", colour_set: "" }];
        return { ...prev, [domId]: { ...quote, tags: newTags } };
    });
}
```

**Step 3 — Fire-and-forget API call:** The change syncs to the server without waiting:

```typescript
// frontend/src/utils/api.ts
export function putTags(tagsMap: Record<string, string[]>): void {
    firePut(`/projects/${projectId()}/tags`, tagsMap);
}

function firePut(path: string, body: unknown): void {
    fetch(`${apiBase()}${path}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
    }).catch(() => {});   // Silently swallow errors
}
```

**Step 4 — Server-side persistence:**

```python
# bristlenose/server/routes/data.py
@router.put("/projects/{project_id}/tags")
def put_tags(project_id: int, tags_map: dict, db: Session = Depends(_get_db)):
    try:
        for dom_id, tag_names in tags_map.items():
            quote = _resolve_quote(db, project_id, dom_id)
            if not quote:
                continue

            # Clear existing user tags for this quote
            db.query(QuoteTag).filter_by(quote_id=quote.id).delete()

            # Create new tags
            for tag_name in tag_names:
                tag_def = (db.query(TagDefinition)
                    .filter(func.lower(TagDefinition.name) == tag_name.lower())
                    .first())
                if not tag_def:
                    # Auto-create tag definition in "Uncategorised" group
                    tag_def = TagDefinition(name=tag_name, codebook_group_id=uncategorised.id)
                    db.add(tag_def)
                    db.flush()

                db.add(QuoteTag(quote_id=quote.id, tag_definition_id=tag_def.id))

        db.commit()
    finally:
        db.close()
```

**Step 5 — SQLite rows created:**

```sql
-- TagDefinition row (if "simplicity" didn't exist yet)
INSERT INTO tag_definition (id, codebook_group_id, name) VALUES (42, 1, 'simplicity');

-- QuoteTag row (links quote to tag)
INSERT INTO quote_tag (quote_id, tag_definition_id) VALUES (7, 42);
```

**The full round-trip:** Keystroke → React state → optimistic UI update → fire-and-forget PUT → FastAPI route → SQLAlchemy upsert → SQLite write. The user sees the tag appear instantly (optimistic update). If the server is down, the tag still appears locally — it just won't persist across sessions.

### 9.4 Video Player Sync

The researcher clicks the timecode `00:12` on Alice's quote. Here's what happens:

```typescript
// frontend/src/components/TimecodeLink.tsx
export function TimecodeLink({ participantId, seconds }: Props) {
    return (
        <a
            className="timecode"
            href="#"
            onClick={(e) => {
                e.preventDefault();
                window.seekTo?.(participantId, seconds);  // Call vanilla JS global
            }}
        >
            {formatTimecode(seconds)}
        </a>
    );
}
```

The `seekTo()` function is defined in vanilla JS (not React):

```javascript
// bristlenose/theme/js/player.js
function seekTo(pid, seconds) {
    const session = _pidToSession[pid];
    const videoUrl = BRISTLENOSE_VIDEO_MAP[session];

    if (!_playerWindow || _playerWindow.closed) {
        // Open popout player window
        _playerWindow = window.open(
            `/report/assets/bristlenose-player.html?src=${encodeURIComponent(videoUrl)}`,
            "bristlenose-player",
            "width=640,height=480"
        );
    }
    // Post message to player to seek
    _playerWindow.postMessage({ action: "seek", time: seconds }, "*");
}
```

A separate browser window opens with the video, seeked to 00:12. The timecode link glows (`.bn-timecode-glow` CSS class) to show which quote is currently playing.

---

## Part 10: Codebooks — The Tag Taxonomy

### 10.1 What Codebooks Are

**Plain language:** A codebook is a predefined set of tags organised into groups. Instead of researchers inventing tags on the fly ("simplicity", "easy", "simple" — three tags for the same concept), a codebook provides a curated vocabulary.

**Technical:** YAML files in `bristlenose/server/codebook/` define tag taxonomies. Four ship with Bristlenose:

| Framework | Focus | Example tags |
|-----------|-------|-------------|
| UXR | General user research | workaround, adaptation, mental model, trust signal |
| Norman | Don Norman's design principles | affordance, mapping, feedback, constraint |
| Garrett | Jesse James Garrett's UX layers | strategy, scope, structure, skeleton, surface |
| Plato | Cognitive models | recognition, recall, cognitive load, error recovery |

### 10.2 YAML Structure

```yaml
# bristlenose/server/codebook/uxr.yaml
id: uxr
title: Bristlenose UXR Codebook
enabled: true

groups:
  - name: Behaviour
    subtitle: What people actually do
    colour_set: ux                     # Maps to --bn-ux-* CSS variables
    tags:
      - name: workaround
        definition: >
          The participant has invented their own solution to compensate
          for a gap in the product's design.
        apply_when: >
          The participant describes doing something "the wrong way" or
          "my own way" to achieve a goal the product doesn't support directly.
        not_this: >
          A mistake or accident. A workaround is deliberate.
```

**The `apply_when` and `not_this` fields are discrimination prompts** — they're sent to the LLM during AutoCode to help it distinguish similar tags. These are carefully written to match how researchers think about the difference between, say, a "workaround" and an "adaptation."

### 10.3 AutoCode: LLM-Assisted Tagging

**What happens:** The researcher clicks "✦ AutoCode" on a framework. The LLM reads every quote, reads every tag definition (including `apply_when`/`not_this`), and proposes the best-matching tag for each quote with a confidence score.

**The flow:**

```
Researcher clicks "✦ AutoCode" on UXR framework
    ↓
POST /api/projects/1/autocode/uxr
    ↓
AutoCodeJob created (status: "pending")
    ↓
Background task starts: run_autocode_job()
    ↓
Load all quotes + UXR tag taxonomy with discrimination prompts
    ↓
Batch quotes into groups of 25
    ↓
For each batch:
    Format taxonomy:
        "### Behaviour — What people actually do
         **workaround** — The participant has invented their own solution...
           Apply when: The participant describes doing something 'the wrong way'...
           Not this: A mistake or accident. A workaround is deliberate."
    ↓
    LLM call: "Which tag best fits each quote?"
    ↓
    LLM returns: [
        {quote_index: 0, tag_name: "workaround", confidence: 0.87, rationale: "..."},
        {quote_index: 1, tag_name: "mental model", confidence: 0.72, rationale: "..."},
    ]
    ↓
    Create ProposedTag rows in SQLite
    ↓
AutoCodeJob status → "completed"
    ↓
Frontend polls GET /autocode/uxr/status (every 2 seconds)
    ↓
Status = completed → show report modal with proposals
    ↓
Researcher reviews proposals with confidence slider
    ↓
"Accept" → POST /autocode/proposals/{id}/accept → creates QuoteTag
"Deny"   → POST /autocode/proposals/{id}/deny → kept for analytics
```

For our Hello World study, AutoCode might propose:

| Quote | Proposed tag | Confidence | Rationale |
|-------|-------------|------------|-----------|
| Alice: "You just say what you mean and Python does it" | mental model | 0.82 | "Participant reveals how they think about the language — as a translation of thought to code" |
| Bob: "If it compiles, it works" | trust signal | 0.91 | "Participant expresses deep trust in the compiler's guarantees" |

---

## Part 11: The Analysis Page — Signal Detection

### 11.1 What Signals Are

**Plain language:** A signal is a statistically notable pattern — like "frustration is unusually concentrated in the checkout section." The analysis page surfaces these automatically so researchers don't have to manually count quotes.

**Technical:** The analysis module builds a matrix (sections × sentiments), computes concentration ratios, and identifies cells where the observed frequency is significantly higher than expected by chance.

### 11.2 The Math

For our tiny study, the matrix might look like:

```
                    delight  confidence  (total)
Hello World Code       1          1         2
Language philosophy    1          1         2
(total)                2          2         4
```

**Concentration ratio** for "delight in Hello World Code":

```
observed = 1/2 = 0.5    (1 delight quote out of 2 quotes in this section)
expected = 2/4 = 0.5    (2 delight quotes out of 4 total quotes)
ratio = 0.5/0.5 = 1.0   (exactly what we'd expect — no signal)
```

With our 2-session study, everything is evenly distributed — no real signals emerge. But with 10+ sessions, you'd see patterns like "frustration concentrates at 3× expected in the error handling section" — that's a strong signal worth investigating.

### 11.3 Rendering

**Python side — data injection:**

```python
# bristlenose/stages/render_html.py
analysis_json = _serialize_analysis(analysis)
parts.append(f"<script>window.BRISTLENOSE_ANALYSIS = {analysis_json};</script>")
```

**React side — AnalysisPage island:**

```typescript
// frontend/src/islands/AnalysisPage.tsx
export function AnalysisPage({ projectId }: { projectId: string }) {
    // Sentiment data from baked window global (fast, no API call)
    const sentimentData = (window as any).BRISTLENOSE_ANALYSIS;

    // Tag data from API (computed per-codebook)
    const [tagData, setTagData] = useState(null);
    useEffect(() => {
        getCodebookAnalysis(projectId).then(setTagData);
    }, [projectId]);

    return (
        <div className="analysis-page">
            {signals.map(signal => (
                <SignalCard
                    key={signal.location + signal.sentiment}
                    location={signal.location}
                    sentiment={signal.sentiment}
                    concentration={signal.concentration}
                    confidence={signal.confidence}
                    participants={signal.participants}
                    quotes={signal.quotes}
                />
            ))}
            <Heatmap matrix={sectionMatrix} sentiments={sentiments} />
        </div>
    );
}
```

**Heatmap colouring uses OKLCH** — a perceptually uniform colour space:

```css
/* bristlenose/theme/organisms/analysis.css */
.bn-analysis-cell {
    /* Computed in JS based on concentration ratio */
    background-color: oklch(
        var(--bn-heat-l)        /* Lightness: 95% (low) to 45% (high) */
        var(--bn-heat-chroma)   /* 0.12 (constant saturation) */
        var(--bn-heat-h)        /* Hue: per-sentiment (frustration=55°, delight=165°) */
    );
}
```

Higher concentration → darker cell. The perceptual uniformity of OKLCH means "twice as dark" always means "twice the signal strength," regardless of hue.

---

## Part 12: The People File — Participant Registry

### 12.1 What It Is

**Plain language:** A YAML file where researchers record participant names, roles, and personas. Bristlenose auto-generates it from LLM-extracted data; researchers refine it.

```yaml
# hello-world-study/bristlenose-output/people.yaml
participants:
  p1:
    computed:
      participant_id: p1
      session_id: s1
      session_date: 2026-02-21
      duration_seconds: 62.5
      words_spoken: 87
      pct_words: 68.0
      source_file: GMT20260221-140000_Recording.mp4
    editable:
      full_name: Alice
      short_name: Alice
      role: Software Engineer
      persona: ""
      notes: ""
  p2:
    computed:
      participant_id: p2
      session_id: s2
      duration_seconds: 58.3
      words_spoken: 92
    editable:
      full_name: Bob
      short_name: Bob
      role: Systems Programmer
```

**`computed`** fields are pipeline-generated and overwritten on re-runs. **`editable`** fields are researcher-owned and never touched by the pipeline.

---

## Part 13: The Vite Build — From TypeScript to Browser

### 13.1 Build Pipeline

```bash
npm run build
# 1. tsc -b           → Type-checks ALL TypeScript (including test files)
# 2. vite build       → Bundles for production
# 3. Output:          → bristlenose/server/static/assets/index-{hash}.js
#                     → bristlenose/server/static/assets/index-{hash}.css
```

**Vite config:**

```typescript
// frontend/vite.config.ts
export default defineConfig({
    plugins: [react()],
    build: {
        outDir: "../bristlenose/server/static",
        emptyOutDir: true,
    },
    server: {
        port: 5173,
        proxy: {
            "/api": "http://localhost:8150",      // Proxy API calls to FastAPI
            "/report": "http://localhost:8150",   // Proxy report files
        },
    },
});
```

**Dev mode workflow:**
```bash
# Terminal 1: Start FastAPI
bristlenose serve --dev hello-world-study/

# Terminal 2: Start Vite dev server
cd frontend && npm run dev
# → http://localhost:5173 with hot reload
# → API calls proxied to :8150
```

### 13.2 TypeScript → React → DOM

**Type safety chain:**

```
Pydantic model (Python)          → JSON response         → TypeScript interface
ExtractedQuote(BaseModel)        → {"sentiment": "..."}  → QuoteResponse
ScreenCluster(BaseModel)         → {"screen_label":"..."}→ SectionResponse
```

**The interfaces mirror the Pydantic models:**

```typescript
// frontend/src/utils/types.ts
interface QuoteResponse {
    dom_id: string;              // "q-p1-12"
    text: string;
    sentiment: string | null;    // "delight"
    intensity: number;           // 2
    participant_id: string;      // "p1"
    speaker_name: string;        // "Alice"
    start_timecode: number;      // 12.0
    is_starred: boolean;
    is_hidden: boolean;
    tags: TagResponse[];
    proposed_tags: ProposedTagResponse[];
}

interface SectionResponse {
    cluster_id: number;
    screen_label: string;        // "Hello World Code"
    description: string;
    display_order: number;
    quotes: QuoteResponse[];
}
```

---

## Part 14: Complete Data Flow Diagram

Here is the entire journey of Alice's "simplicity" quote, from audio wave to browser pixel:

```
                     STAGE 1: INGEST
Zoom .mp4 file ──────────────────────────►  InputSession(s1, files=[.mp4, .vtt])
Zoom .vtt file ─┘

                     STAGE 3: PARSE VTT
.vtt file ───────────────────────────────►  TranscriptSegment(start=12.0, text="So my favourite...")

                     STAGE 5b: SPEAKER ID (LLM Call #1)
Segments ─────── Claude API ─────────────►  SpeakerInfo(role=PARTICIPANT, name="Alice")
                                            Segments updated: speaker_code="p1"

                     STAGE 6: MERGE
Segments ────────────────────────────────►  FullTranscript(session_id="s1", segments=[...])
                                            Written to: transcripts-raw/s1.txt

                     STAGE 8: TOPIC SEGMENTATION (LLM Call #2)
Transcript ──── Claude API ──────────────►  SessionTopicMap(boundaries=[
                                                TopicBoundary(5.0, "Hello World in Python"),
                                                TopicBoundary(25.0, "Language philosophy"),
                                            ])
                                            Cached to: intermediate/topic_boundaries.json

                     STAGE 9: QUOTE EXTRACTION (LLM Call #3)
Transcript ──── Claude API ──────────────►  ExtractedQuote(
+ Topics                                        text="What I love about Python...",
                                                sentiment=DELIGHT,
                                                quote_type=GENERAL_CONTEXT,
                                                segment_index=3,
                                            )
                                            Cached to: intermediate/extracted_quotes.json

                     STAGE 11: THEMATIC GROUPING (LLM Call #4)
Quotes ──────── Claude API ──────────────►  ThemeGroup(
                                                theme_label="Language philosophy",
                                                quotes=[alice_quote, bob_quote],
                                            )
                                            Cached to: intermediate/theme_groups.json

                     STAGE 12: RENDER HTML
ThemeGroup ──────────────────────────────►  <blockquote id="q-p1-12">
+ FullTranscript                                "What I love about Python..."
+ PeopleFile                                </blockquote>
                                            Written to: bristlenose-hello-world-study-report.html

                     SERVE MODE: IMPORT
intermediate/*.json ─────────────────────►  SQLite rows:
                                                Quote(id=7, text="...", sentiment="delight")
                                                ThemeQuote(theme_id=1, quote_id=7)

                     SERVE MODE: INJECT REACT
Static HTML ─── re.sub() ───────────────►  <div id="bn-quote-themes-root" data-project-id="1">

                     BROWSER: REACT MOUNT
Mount div ─── createRoot().render() ─────►  <QuoteThemes projectId="1" />

                     BROWSER: API FETCH
QuoteThemes ──── GET /api/projects/1/quotes ─►  JSON response with quote data

                     BROWSER: RENDER
JSON ─── React reconciliation ───────────►  <QuoteCard quote={...} />
                                                <Badge text="delight" variant="ai" />

                     BROWSER: USER INTERACTION
Click ★ ─── React state update ──────────►  { isStarred: true }
         └── fire-and-forget PUT ────────►  QuoteState(quote_id=7, is_starred=true)
                                            SQLite row persisted
```

---

## Part 15: The Numbers

For our Hello World study (2 sessions, ~2 minutes total):

| Metric | Value |
|--------|-------|
| **Input files** | 3 (2 .mp4, 1 .vtt) |
| **Sessions** | 2 |
| **Participants** | 2 (Alice, Bob) |
| **Transcript segments** | ~34 |
| **LLM calls** | 4 (speaker ID × 2, topics × 2, quotes × 2, cluster + theme × 2) |
| **Approximate tokens** | ~8,000 input, ~3,000 output |
| **Estimated cost** | ~$0.02 (Claude Sonnet) |
| **Extracted quotes** | ~8 |
| **Sections** | ~1 |
| **Themes** | ~1 |
| **SQLite tables** | 24 |
| **SQLite rows** | ~50 |
| **CSS files concatenated** | 42 |
| **JS modules loaded** | 23 (report) or 5 (transcript) |
| **React components rendered** | ~7 islands, ~16 primitives |
| **Total pipeline time** | ~13 seconds |

For a real 10-session study (~30 min each), multiply tokens by ~50×, cost by ~50×, and time by ~5× (LLM calls dominate, and they're concurrent).

---

## Epilogue: What Makes This Architecture Work

**For the researcher:** Bristlenose turns hours of manual quote-pulling into 15 minutes of automated analysis. The report is immediately useful — quotes are attributed, sentiments are tagged, themes emerge. The researcher's job shifts from extraction to interpretation.

**For the engineer:** The architecture is shaped by three constraints:

1. **Local-first:** No data leaves the machine. This rules out cloud databases, server-side rendering farms, and hosted LLM APIs for transcription (Whisper runs locally).

2. **Resumable:** LLM calls are expensive. The manifest + intermediate JSON system means you never pay twice for the same work. A crash at Stage 11 loses zero progress from Stages 1–10.

3. **Progressive enhancement:** The static HTML report works offline with vanilla JS. Serve mode adds React islands for richer interaction. The same CSS tokens power both. This isn't an accident — it's how you migrate a working product without breaking it.

The Hello World study is trivially small. But the architecture handles 50-session studies with 20-hour transcripts and 500+ quotes using the same pipeline, the same database schema, the same React components. The only things that scale are LLM tokens (linear with transcript length) and rendering time (linear with quote count). Everything else is O(1).

That's the whole stack. From a `.mp4` file to a `<blockquote>` in your browser and back again when you click ★.
