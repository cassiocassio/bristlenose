/**
 * The report header's redaction line.
 *
 * Until 13 Sep 2026 there was no user-visible sign anywhere that a project had
 * been PII-redacted — not in the SPA, the report, the export, the static
 * renderer or the Mac. This is the one surface that says so.
 *
 * Two rules it must keep, and they are the whole point:
 *
 *  - **Silent when false.** A "not redacted" line on every report is noise,
 *    and faintly alarming to a client who never asked the question. Absence is
 *    information.
 *  - **Never in the export dialog.** Redaction and the export "Anonymise"
 *    checkbox sound alike and are not alike — one is a pipeline-time fact
 *    about transcript text, the other an export-time choice about display
 *    names. Keeping redaction out of the export surfaces entirely is what
 *    stops them being read as one setting.
 */
import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Header } from "./Header";

vi.mock("../utils/api", () => ({ apiGet: vi.fn() }));
vi.mock("../hooks/useProjectId", () => ({ useProjectId: () => 1 }));
vi.mock("../utils/exportData", () => ({
  isExportMode: () => false,
  getExportData: () => undefined,
}));

import { apiGet } from "../utils/api";

const mockApiGet = vi.mocked(apiGet);

function info(overrides: Record<string, unknown> = {}) {
  return {
    project_name: "Acme onboarding study",
    session_count: 6,
    participant_count: 5,
    ...overrides,
  };
}

describe("Header — redaction line", () => {
  beforeEach(() => {
    mockApiGet.mockReset();
  });

  it("states it, and links the term to the docs, when the run redacted", async () => {
    mockApiGet.mockResolvedValue(info({ pii_redacted: true }));
    render(<Header />);

    await waitFor(() =>
      expect(screen.getByText(/Personally Identifiable Information/)).toBeTruthy(),
    );

    // "redacted" is the link — the term is industry-standard for researchers,
    // and the docs page carries the detail rather than the header.
    const link = screen.getByRole("link", { name: "redacted" });
    expect(link.getAttribute("href")).toBe(
      "https://bristlenose.app/docs/redact-pii.html",
    );
    expect(link.getAttribute("rel")).toContain("noopener");
  });

  it("says nothing at all when the run did not redact", async () => {
    mockApiGet.mockResolvedValue(info({ pii_redacted: false }));
    render(<Header />);

    await waitFor(() => expect(screen.getByText(/6 sessions/)).toBeTruthy());
    expect(screen.queryByText(/Personally Identifiable Information/)).toBeNull();
    expect(screen.queryByRole("link", { name: "redacted" })).toBeNull();
  });

  it("says nothing when the field is absent entirely", async () => {
    // An older server, or an export embed baked before the field existed.
    // The header must degrade to silence, never to a claim.
    mockApiGet.mockResolvedValue(info());
    render(<Header />);

    await waitFor(() => expect(screen.getByText(/6 sessions/)).toBeTruthy());
    expect(screen.queryByText(/Personally Identifiable Information/)).toBeNull();
  });

  it("still renders the session and participant counts alongside it", async () => {
    mockApiGet.mockResolvedValue(info({ pii_redacted: true }));
    render(<Header />);

    await waitFor(() => expect(screen.getByText(/6 sessions/)).toBeTruthy());
    expect(screen.getByText(/5 participants/)).toBeTruthy();
  });
});
