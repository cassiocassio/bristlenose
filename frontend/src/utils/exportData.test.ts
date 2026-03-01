import { describe, it, expect, afterEach } from "vitest";
import {
  isExportMode,
  getExportData,
  resolveFromExport,
  _resetExportCache,
} from "./exportData";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function setExportGlobal(data: unknown): void {
  (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = data;
}

function clearExportGlobal(): void {
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
}

const MOCK_EXPORT = {
  version: 1,
  exported_at: "2026-03-01T12:00:00Z",
  project: { project_name: "Test", session_count: 2, participant_count: 3 },
  health: { status: "ok", version: "0.11.1" },
  dashboard: { stats: { session_count: 2 } },
  sessions: { sessions: [{ session_id: "s1" }] },
  quotes: { sections: [], themes: [], total_quotes: 5 },
  codebook: { groups: [], ungrouped: [], all_tag_names: [] },
  analysis: {
    sentiment: { signals: [], totalParticipants: 3 },
    codebooks: { codebooks: [], total_participants: 3, trade_off_note: "" },
  },
  transcripts: {
    s1: { session_id: "s1", segments: [] },
    s2: { session_id: "s2", segments: [] },
  },
  people: { p1: { full_name: "Alice", short_name: "A", role: "Manager" } },
  videoMap: null,
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("exportData", () => {
  afterEach(() => {
    clearExportGlobal();
    _resetExportCache();
  });

  // ── Detection ──────────────────────────────────────────────────────────

  describe("isExportMode", () => {
    it("returns false when no global is set", () => {
      expect(isExportMode()).toBe(false);
    });

    it("returns true when BRISTLENOSE_EXPORT is set", () => {
      setExportGlobal(MOCK_EXPORT);
      _resetExportCache();
      expect(isExportMode()).toBe(true);
    });

    it("caches the result", () => {
      setExportGlobal(MOCK_EXPORT);
      _resetExportCache();
      expect(isExportMode()).toBe(true);
      // Remove global — cached result should persist
      clearExportGlobal();
      expect(isExportMode()).toBe(true);
    });
  });

  describe("getExportData", () => {
    it("returns null when not in export mode", () => {
      expect(getExportData()).toBeNull();
    });

    it("returns the export data object", () => {
      setExportGlobal(MOCK_EXPORT);
      _resetExportCache();
      const data = getExportData();
      expect(data).not.toBeNull();
      expect(data!.version).toBe(1);
      expect(data!.project.project_name).toBe("Test");
    });
  });

  // ── Resolver ───────────────────────────────────────────────────────────

  describe("resolveFromExport", () => {
    it("returns null when not in export mode", () => {
      expect(resolveFromExport("/dashboard")).toBeNull();
    });

    describe("with export data", () => {
      afterEach(() => {
        clearExportGlobal();
        _resetExportCache();
      });

      function setup() {
        setExportGlobal(MOCK_EXPORT);
        _resetExportCache();
      }

      it("resolves /info", () => {
        setup();
        expect(resolveFromExport("/info")).toEqual(MOCK_EXPORT.project);
      });

      it("resolves /dashboard", () => {
        setup();
        expect(resolveFromExport("/dashboard")).toEqual(MOCK_EXPORT.dashboard);
      });

      it("resolves /sessions", () => {
        setup();
        expect(resolveFromExport("/sessions")).toEqual(MOCK_EXPORT.sessions);
      });

      it("resolves /quotes", () => {
        setup();
        expect(resolveFromExport("/quotes")).toEqual(MOCK_EXPORT.quotes);
      });

      it("resolves /codebook", () => {
        setup();
        expect(resolveFromExport("/codebook")).toEqual(MOCK_EXPORT.codebook);
      });

      it("resolves /people", () => {
        setup();
        expect(resolveFromExport("/people")).toEqual(MOCK_EXPORT.people);
      });

      it("resolves /video-map", () => {
        setup();
        expect(resolveFromExport("/video-map")).toBeNull();
      });

      it("resolves /analysis/sentiment", () => {
        setup();
        expect(resolveFromExport("/analysis/sentiment")).toEqual(
          MOCK_EXPORT.analysis.sentiment,
        );
      });

      it("resolves /analysis/codebooks", () => {
        setup();
        expect(resolveFromExport("/analysis/codebooks")).toEqual(
          MOCK_EXPORT.analysis.codebooks,
        );
      });

      it("resolves /analysis/codebooks with query string", () => {
        setup();
        expect(resolveFromExport("/analysis/codebooks?elaborate=true")).toEqual(
          MOCK_EXPORT.analysis.codebooks,
        );
      });

      it("resolves /transcripts/s1", () => {
        setup();
        expect(resolveFromExport("/transcripts/s1")).toEqual(
          MOCK_EXPORT.transcripts.s1,
        );
      });

      it("resolves /transcripts/s2", () => {
        setup();
        expect(resolveFromExport("/transcripts/s2")).toEqual(
          MOCK_EXPORT.transcripts.s2,
        );
      });

      it("returns null for unknown transcript", () => {
        setup();
        expect(resolveFromExport("/transcripts/s99")).toBeNull();
      });

      it("returns null for unrecognised paths", () => {
        setup();
        expect(resolveFromExport("/unknown")).toBeNull();
        expect(resolveFromExport("/codebook/templates")).toBeNull();
        expect(resolveFromExport("/autocode/abc/status")).toBeNull();
      });
    });
  });
});
