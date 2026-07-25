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
  version: 2,
  exported_at: "2026-03-01T12:00:00Z",
  health: {
    status: "ok",
    version: "0.11.1",
    links: {
      github_issues_url: "https://github.com/cassiocassio/bristlenose/issues/new",
    },
    feedback: {
      enabled: true,
      url: "https://bristlenose.app/feedback.php",
    },
  },
  logos: { light: "data:image/png;base64,AAAA", dark: "data:image/png;base64,BBBB" },
  endpoints: {
    "/info": { project_name: "Test", session_count: 2, participant_count: 3 },
    "/dashboard": { stats: { session_count: 2 } },
    "/sessions": { sessions: [{ session_id: "s1" }] },
    "/quotes": { sections: [], themes: [], total_quotes: 5 },
    "/codebook": { groups: [], ungrouped: [], all_tag_names: [] },
    "/people": { p1: { full_name: "Alice", short_name: "A", role: "Manager" } },
    "/video-map": null,
    "/analysis/sentiment": { signals: [], totalParticipants: 3 },
    "/analysis/codebooks": { codebooks: [], total_participants: 3, trade_off_note: "" },
    "/framework-states": { garrett: false },
    "/hidden-tag-groups": ["Ungrouped"],
    "/transcripts/s1": { session_id: "s1", segments: [] },
    "/transcripts/s2": { session_id: "s2", segments: [] },
    "/quotes/q-p1-10/moderator-question": {
      text: "What did you expect?",
      speaker_code: "m1",
      start_time: 5,
      end_time: 8,
      segment_index: 3,
    },
  },
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
      expect(data!.version).toBe(2);
      expect(data!.endpoints["/info"]).toEqual(MOCK_EXPORT.endpoints["/info"]);
    });
  });

  // ── Resolver ───────────────────────────────────────────────────────────

  describe("resolveFromExport", () => {
    it("returns undefined when not in export mode", () => {
      expect(resolveFromExport("/dashboard")).toBeUndefined();
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
        expect(resolveFromExport("/info")).toEqual(MOCK_EXPORT.endpoints["/info"]);
      });

      it("resolves /dashboard", () => {
        setup();
        expect(resolveFromExport("/dashboard")).toEqual(
          MOCK_EXPORT.endpoints["/dashboard"],
        );
      });

      it("resolves /sessions", () => {
        setup();
        expect(resolveFromExport("/sessions")).toEqual(
          MOCK_EXPORT.endpoints["/sessions"],
        );
      });

      it("resolves /quotes", () => {
        setup();
        expect(resolveFromExport("/quotes")).toEqual(MOCK_EXPORT.endpoints["/quotes"]);
      });

      it("resolves /codebook", () => {
        setup();
        expect(resolveFromExport("/codebook")).toEqual(
          MOCK_EXPORT.endpoints["/codebook"],
        );
      });

      it("resolves /people", () => {
        setup();
        expect(resolveFromExport("/people")).toEqual(MOCK_EXPORT.endpoints["/people"]);
      });

      it("resolves the newly-embedded view-state endpoints", () => {
        setup();
        expect(resolveFromExport("/framework-states")).toEqual(
          MOCK_EXPORT.endpoints["/framework-states"],
        );
        expect(resolveFromExport("/hidden-tag-groups")).toEqual(
          MOCK_EXPORT.endpoints["/hidden-tag-groups"],
        );
      });

      it("resolves an embedded moderator-question", () => {
        setup();
        expect(resolveFromExport("/quotes/q-p1-10/moderator-question")).toEqual(
          MOCK_EXPORT.endpoints["/quotes/q-p1-10/moderator-question"],
        );
      });

      it("resolves /video-map as present-null (not a miss)", () => {
        setup();
        expect(resolveFromExport("/video-map")).toBeNull();
      });

      it("resolves /analysis/sentiment", () => {
        setup();
        expect(resolveFromExport("/analysis/sentiment")).toEqual(
          MOCK_EXPORT.endpoints["/analysis/sentiment"],
        );
      });

      it("resolves /analysis/codebooks", () => {
        setup();
        expect(resolveFromExport("/analysis/codebooks")).toEqual(
          MOCK_EXPORT.endpoints["/analysis/codebooks"],
        );
      });

      it("resolves /analysis/codebooks with query string", () => {
        setup();
        expect(resolveFromExport("/analysis/codebooks?elaborate=true")).toEqual(
          MOCK_EXPORT.endpoints["/analysis/codebooks"],
        );
      });

      it("resolves /transcripts/s1", () => {
        setup();
        expect(resolveFromExport("/transcripts/s1")).toEqual(
          MOCK_EXPORT.endpoints["/transcripts/s1"],
        );
      });

      it("resolves /transcripts/s2", () => {
        setup();
        expect(resolveFromExport("/transcripts/s2")).toEqual(
          MOCK_EXPORT.endpoints["/transcripts/s2"],
        );
      });

      it("returns undefined for unknown transcript", () => {
        setup();
        expect(resolveFromExport("/transcripts/s99")).toBeUndefined();
      });

      it("returns undefined for unrecognised paths", () => {
        setup();
        expect(resolveFromExport("/unknown")).toBeUndefined();
        expect(resolveFromExport("/codebook/templates")).toBeUndefined();
        expect(resolveFromExport("/autocode/abc/status")).toBeUndefined();
      });
    });
  });
});
