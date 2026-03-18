/** Developer section — architecture, stack, APIs, dev tools. */

import type { DevInfoResponse } from "./types";

export function DeveloperSection({ info }: { info: DevInfoResponse | null }) {
  return (
    <>
      <h3>Architecture</h3>
      <p>
        Twelve-stage pipeline: ingest &rarr; audio extraction &rarr; transcript
        parsing &rarr; transcription &rarr; speaker identification &rarr;
        transcript merge &rarr; PII removal &rarr; topic segmentation &rarr;
        quote extraction &rarr; quote clustering &rarr; thematic grouping &rarr;
        render. Transcription runs locally (Whisper via MLX or faster-whisper).
        Analysis stages call the configured LLM provider. Analysis page metrics
        are pure math &mdash; no LLM calls.
      </p>

      <h3>Stack</h3>
      <dl>
        <dt>CLI &amp; pipeline</dt>
        <dd>Python 3.10+, Pydantic, FFmpeg, Whisper</dd>
        <dt>Serve mode</dt>
        <dd>FastAPI, SQLAlchemy, SQLite (WAL mode), Uvicorn</dd>
        <dt>Frontend</dt>
        <dd>React 18, TypeScript, Vite, React Router</dd>
        <dt>Desktop</dt>
        <dd>SwiftUI macOS shell, PyInstaller sidecar</dd>
        <dt>Linting &amp; types</dt>
        <dd>Ruff, mypy, Vitest, tsc</dd>
        <dt>Packaging</dt>
        <dd>PyPI, Homebrew, Snap</dd>
      </dl>

      <h3>Key APIs</h3>
      <p>
        Serve mode exposes a project-scoped REST API. Sessions, quotes, tags,
        people, and autocode endpoints support the React SPA. The analysis
        module computes signal concentration, agreement breadth, and composite
        scores as plain dataclasses &mdash; ephemeral, never persisted. Static
        render produces a self-contained HTML file with JSON data in an IIFE.
      </p>

      {info && (
        <>
          <h3>Dev tools</h3>
          <dl>
            <dt>Database</dt>
            <dd>
              <code>{info.db_path}</code>
            </dd>
            <dt>Schema</dt>
            <dd>{info.table_count} tables</dd>
            <dt>Renderer overlay</dt>
            <dd>
              Press <kbd>&sect;</kbd> to colour-code regions by renderer
              (blue&nbsp;=&nbsp;Jinja2, green&nbsp;=&nbsp;React,
              amber&nbsp;=&nbsp;Vanilla&nbsp;JS)
            </dd>
          </dl>
          <ul>
            {info.endpoints.map((ep) => (
              <li key={ep.url}>
                <a href={ep.url} target="_blank" rel="noopener noreferrer">
                  {ep.label}
                </a>{" "}
                &mdash; {ep.description}
              </li>
            ))}
          </ul>
        </>
      )}
    </>
  );
}
