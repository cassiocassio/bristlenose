/** Design section — design system, dark mode, component library, mockups. */

import type { DesignSectionData } from "./types";

export function DesignSection({ sections }: { sections: DesignSectionData[] | undefined }) {
  return (
    <>
      <h3>Design system</h3>
      <p>
        Atomic CSS architecture with five layers: <strong>tokens</strong>{" "}
        (colours, spacing, typography as CSS custom properties),{" "}
        <strong>atoms</strong> (badge, button, input, timecode, toggle,
        thumbnail), <strong>molecules</strong> (person badge, tag input,
        editable text, sparkline), <strong>organisms</strong> (quote card,
        toolbar, codebook panel, analysis grid), and{" "}
        <strong>templates</strong> (report, transcript, print layouts). All
        values flow from tokens &mdash; nothing is hardcoded.
      </p>

      <h3>Dark mode</h3>
      <p>
        All-CSS via the <code>light-dark()</code> function on every colour
        token. No JavaScript toggle &mdash; follows the system preference
        (<code>prefers-color-scheme</code>). Every component inherits both
        themes automatically.
      </p>

      <h3>Component library</h3>
      <p>
        Sixteen React primitives: Badge, PersonBadge, TimecodeLink,
        EditableText, Toggle, Modal, Toast, TagInput, Sparkline, Metric,
        JourneyChain, Annotation, Counter, Thumbnail, MicroBar, and
        ConfirmDialog. Seven of these cover 80% of the app surface. Each React
        component name matches its CSS file (e.g. <code>Badge.tsx</code> &rarr;{" "}
        <code>atoms/badge.css</code>).
      </p>

      <h3>Typography</h3>
      <p>
        Inter Variable with four semantic weights: normal (420), emphasis (490),
        starred (520), strong (700). Tabular numbers for timecodes and
        statistics. System serif fallback for academic citations.
      </p>

      {sections && sections.length > 0 && (
        <>
          <h3>Mockups &amp; experiments</h3>
          {sections.map((section) => (
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
