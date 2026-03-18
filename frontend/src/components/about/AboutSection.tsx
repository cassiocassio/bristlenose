/** About section — product guide, feature descriptions, footer links. */

export function AboutSection({ version }: { version: string | null }) {
  return (
    <>
      {version && <p>Version {version}</p>}

      <p>
        Open-source interview transcript analysis. Takes a folder of interview
        recordings and produces a report of extracted quotes grouped by screen
        and theme.
      </p>

      <h3>Input</h3>
      <p>
        Video (mp4, mov, avi, mkv, webm), audio (wav, mp3, m4a, flac, ogg, wma,
        aac), or existing transcripts (vtt, srt, docx). Recordings from Zoom,
        Teams, and Google Meet are detected automatically &mdash; files from the
        same session are grouped together. Other sources (Otter.ai, Rev, Loom,
        OBS, Voice Memos) work when exported in any of these formats.
      </p>

      <h3>Transcription and analysis</h3>
      <p>
        Transcription runs locally on your machine. Analysis uses Claude,
        ChatGPT, Gemini, Azure OpenAI, or Ollama (local, free).
      </p>

      <h3>Dashboard</h3>
      <p>
        Overview of the project: participant count, session count, quote totals,
        sentiment distribution. Links to individual sessions.
      </p>

      <h3>Quotes</h3>
      <p>
        All extracted quotes, organised into sections (by screen or task) and
        themes (cross-participant patterns). Star, hide, tag, and edit quotes.
        Filter by tag, search by text, switch between section and theme view.
      </p>

      <h3>Sessions</h3>
      <p>
        List of interview sessions with duration, participant, and thumbnail.
        Click through to the full transcript with timecodes. Click a timecode to
        open the video in a popout player.
      </p>

      <h3>Analysis</h3>
      <p>
        Signal concentration grids &mdash; which themes appear in which
        sessions, and how strongly. Helps identify patterns that cut across
        participants.
      </p>

      <h3>Codebook</h3>
      <p>
        Tag definitions and auto-coded categories. Review and accept or reject
        auto-generated tags.
      </p>

      <h3>Export</h3>
      <p>
        Filter your quotes and export as CSV for use in Miro, FigJam, Mural,
        Lucidspark, or a spreadsheet.
      </p>

      <p>
        Built by Martin Storey (
        <a href="mailto:martin@cassiocassio.co.uk">martin@cassiocassio.co.uk</a>
        ). Free and open source (AGPL-3.0).
      </p>

      <div className="bn-about-footer">
        <a
          href="#"
          onClick={(e) => {
            e.preventDefault();
            document.dispatchEvent(new KeyboardEvent("keydown", { key: "?" }));
          }}
        >
          Keyboard shortcuts
        </a>
        {" "}
        &middot;{" "}
        <a
          href="https://github.com/cassiocassio/bristlenose/issues/new"
          target="_blank"
          rel="noopener noreferrer"
        >
          Report a bug
        </a>
        {" "}
        &middot;{" "}
        <a
          href="https://github.com/cassiocassio/bristlenose"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
      </div>
    </>
  );
}
