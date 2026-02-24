/**
 * AboutPanel — React island for the About tab.
 *
 * Replaces inline Jinja2 HTML in render_html.py (lines 545–592) and
 * absorbs the AboutDeveloper island. Shows version info, keyboard
 * shortcuts, feedback link, and (in dev mode) developer tools.
 */

import { useEffect, useState } from "react";
import { AboutDeveloper } from "./AboutDeveloper";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface HealthResponse {
  status: string;
  version: string;
}

// ---------------------------------------------------------------------------
// Keyboard shortcuts data
// ---------------------------------------------------------------------------

interface ShortcutGroup {
  title: string;
  shortcuts: { keys: string; description: string }[];
}

const SHORTCUT_GROUPS: ShortcutGroup[] = [
  {
    title: "Navigation",
    shortcuts: [
      { keys: "j / ↓", description: "Next quote" },
      { keys: "k / ↑", description: "Previous quote" },
    ],
  },
  {
    title: "Selection",
    shortcuts: [
      { keys: "x", description: "Toggle select" },
      { keys: "Shift+j/k", description: "Extend" },
    ],
  },
  {
    title: "Actions",
    shortcuts: [
      { keys: "s", description: "Star quote(s)" },
      { keys: "h", description: "Hide quote(s)" },
      { keys: "t", description: "Add tag(s)" },
      { keys: "Enter", description: "Play in video" },
    ],
  },
  {
    title: "Global",
    shortcuts: [
      { keys: "/", description: "Search" },
      { keys: "?", description: "This help" },
      { keys: "Esc", description: "Close / clear" },
    ],
  },
];

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function KeyboardShortcuts() {
  return (
    <>
      <h3>Keyboard Shortcuts</h3>
      <div className="help-columns">
        {SHORTCUT_GROUPS.map((group) => (
          <div key={group.title} className="help-section">
            <h3>{group.title}</h3>
            <dl>
              {group.shortcuts.map((sc) => (
                <div key={sc.keys} style={{ display: "contents" }}>
                  <dt>
                    {sc.keys.split(/( \/ | ?\+ ?)/).map((part, i) => {
                      const trimmed = part.trim();
                      if (trimmed === "/" || trimmed === "+") {
                        return <span key={i}>{trimmed === "+" ? "+" : " / "}</span>;
                      }
                      return <kbd key={i}>{trimmed}</kbd>;
                    })}
                  </dt>
                  <dd>{sc.description}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function AboutPanel() {
  const [version, setVersion] = useState<string | null>(null);

  useEffect(() => {
    const apiBase = (window as unknown as Record<string, unknown>).BRISTLENOSE_API_BASE;
    if (typeof apiBase !== "string") return;

    // Health endpoint is at the root, not under project API base
    fetch("/api/health")
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data: HealthResponse) => setVersion(data.version))
      .catch(() => {
        // Silent — version just won't display
      });
  }, []);

  return (
    <div className="bn-about">
      <h2>About Bristlenose</h2>
      <p>
        {version ? `Version ${version}` : "Bristlenose"} &middot;{" "}
        <a
          href="https://github.com/cassiocassio/bristlenose"
          target="_blank"
          rel="noopener noreferrer"
        >
          GitHub
        </a>
      </p>
      <KeyboardShortcuts />
      <hr />
      <h3>Feedback</h3>
      <p>
        <a
          href="https://github.com/cassiocassio/bristlenose/issues/new"
          target="_blank"
          rel="noopener noreferrer"
        >
          Report a bug
        </a>
      </p>
      <AboutDeveloper />
    </div>
  );
}
