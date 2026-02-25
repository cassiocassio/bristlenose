/**
 * AboutDeveloper — React island for serve-mode developer info.
 *
 * Renders in the About tab when the dev server is running. Shows
 * database path, schema stats, and links to dev tools (SQLAdmin, API docs,
 * health check, etc.).
 *
 * Fetches system info from GET /api/dev/info. Silent on error — if the
 * endpoint isn't available (non-dev mode), renders nothing.
 */

import { useEffect, useState } from "react";

// ---------------------------------------------------------------------------
// API response types
// ---------------------------------------------------------------------------

interface EndpointInfo {
  label: string;
  url: string;
  description: string;
}

interface DesignItem {
  label: string;
  url: string;
}

interface DesignSection {
  heading: string;
  items: DesignItem[];
}

interface DevInfoResponse {
  db_path: string;
  table_count: number;
  endpoints: EndpointInfo[];
  design_sections?: DesignSection[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AboutDeveloper() {
  const [info, setInfo] = useState<DevInfoResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/api/dev/info")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: DevInfoResponse) => setInfo(data))
      .catch(() => setError(true));
  }, []);

  // Silent — dev section simply doesn't appear on error or while loading
  if (error || !info) return null;

  return (
    <>
      <hr />
      <h3>Developer</h3>
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
          (blue&nbsp;=&nbsp;Jinja2, green&nbsp;=&nbsp;React, amber&nbsp;=&nbsp;Vanilla&nbsp;JS)
        </dd>
      </dl>
      <h3>Developer Tools</h3>
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
      {info.design_sections && info.design_sections.length > 0 && (
        <>
          <hr />
          <h3>Design</h3>
          {info.design_sections.map((section) => (
            <div key={section.heading}>
              <h4>{section.heading}</h4>
              <ul>
                {section.items.map((item) => (
                  <li key={item.url}>
                    <a href={item.url} target="_blank" rel="noopener noreferrer">
                      {item.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </>
      )}
    </>
  );
}
