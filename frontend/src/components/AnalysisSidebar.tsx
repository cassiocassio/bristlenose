/**
 * AnalysisSidebar — signal-entry navigation for the Analysis tab left sidebar.
 *
 * Lists rendered signal cards grouped by type (Sentiment → Section/Theme,
 * Codebook tags → Section/Theme). Clicking an entry focuses the signal card
 * and syncs the inspector panel.
 *
 * @module AnalysisSidebar
 */

import { useCallback } from "react";
import { useTranslation } from "react-i18next";
import {
  useAnalysisSignalStore,
  setFocusedSignalKey,
} from "../contexts/AnalysisSignalStore";
import { getGroupBg } from "../utils/colours";
import type { UnifiedSignal } from "../utils/types";

// ── Helpers ──────────────────────────────────────────────────────────

/** Render signal entries for a specific sourceType within a signal list. */
function signalsBySourceType(
  signals: UnifiedSignal[],
  sourceType: "section" | "theme",
): UnifiedSignal[] {
  return signals.filter((s) => s.sourceType === sourceType);
}

// ── Component ────────────────────────────────────────────────────────

export function AnalysisSidebar() {
  const { t } = useTranslation();
  const { sentimentSignals, tagSignals, focusedKey } = useAnalysisSignalStore();

  const handleClick = useCallback((key: string) => {
    setFocusedSignalKey(key);
    window.dispatchEvent(
      new CustomEvent("bn:signal-focus", { detail: { key } }),
    );
  }, []);

  const hasSentiment = sentimentSignals.length > 0;
  const hasTags = tagSignals.length > 0;

  if (!hasSentiment && !hasTags) return null;

  return (
    <div className="toc-sidebar-body">
      {hasSentiment && (
        <>
          <div className="toc-heading">{t("analysis.sentiment")}</div>
          <SignalGroup
            signals={sentimentSignals}
            sourceType="section"
            focusedKey={focusedKey}
            onClick={handleClick}
          />
          <SignalGroup
            signals={sentimentSignals}
            sourceType="theme"
            focusedKey={focusedKey}
            onClick={handleClick}
          />
        </>
      )}
      {hasTags && (
        <>
          <div className="toc-heading">{t("analysis.codebookTags")}</div>
          <SignalGroup
            signals={tagSignals}
            sourceType="section"
            focusedKey={focusedKey}
            onClick={handleClick}
          />
          <SignalGroup
            signals={tagSignals}
            sourceType="theme"
            focusedKey={focusedKey}
            onClick={handleClick}
          />
        </>
      )}
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────

interface SignalGroupProps {
  signals: UnifiedSignal[];
  sourceType: "section" | "theme";
  focusedKey: string | null;
  onClick: (key: string) => void;
}

function SignalGroup({ signals, sourceType, focusedKey, onClick }: SignalGroupProps) {
  const { t } = useTranslation();
  const filtered = signalsBySourceType(signals, sourceType);
  if (filtered.length === 0) return null;

  return (
    <>
      <div className="toc-sub-heading">
        {t(sourceType === "section" ? "analysis.section" : "analysis.theme")}
      </div>
      {filtered.map((s) => (
        <SignalEntry
          key={s.key}
          signal={s}
          active={focusedKey === s.key}
          onClick={onClick}
        />
      ))}
    </>
  );
}

interface SignalEntryProps {
  signal: UnifiedSignal;
  active: boolean;
  onClick: (key: string) => void;
}

function SignalEntry({ signal, active, onClick }: SignalEntryProps) {
  const badgeStyle = signal.colourSet
    ? { backgroundColor: getGroupBg(signal.colourSet) }
    : undefined;
  const badgeClass = signal.colourSet
    ? "badge"
    : `badge badge-${signal.columnLabel}`;

  return (
    <a
      className={`signal-entry${active ? " active" : ""}`}
      role="button"
      tabIndex={0}
      onClick={(e) => {
        e.preventDefault();
        onClick(signal.key);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick(signal.key);
        }
      }}
    >
      <span className="signal-entry-name" title={signal.signalName || signal.location}>
        {signal.signalName || signal.location}
      </span>
      <span className={badgeClass} style={badgeStyle}>
        {signal.columnLabel}
      </span>
    </a>
  );
}
