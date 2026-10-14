import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../utils/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../utils/api")>()),
  apiGet: vi.fn(() => Promise.reject(new Error("no server"))),
}));

import { apiGet } from "../utils/api";
import { _resetExportCache } from "../utils/exportData";
import { ScreensTab } from "./ScreensTab";

afterEach(() => {
  delete (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT;
  _resetExportCache();
});

describe("ScreensTab", () => {
  it("says plainly that an exported report carries no screens, and asks nothing", () => {
    (window as unknown as Record<string, unknown>).BRISTLENOSE_EXPORT = {
      version: 1, exported_at: "2026-10-14T00:00:00Z", health: {}, endpoints: {},
    };
    _resetExportCache();
    const { container } = render(<ScreensTab />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("Screens");
    expect(screen.getByText("Screens aren’t included in an exported report.")).toBeInTheDocument();
    // On the shared datum, like every other state of the lens.
    expect(container.querySelector(":scope > section > .section-heading")).not.toBeNull();
    expect(apiGet).not.toHaveBeenCalled();
  });
});
