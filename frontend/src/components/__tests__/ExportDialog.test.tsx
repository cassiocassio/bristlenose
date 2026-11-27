/**
 * Export report: the language row is a colon label beside its pop-up (v2 form
 * layout, 27 Nov 2026), and the pop-up still decides the locale the export bakes.
 */
import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ExportDialog } from "../ExportDialog";
import i18n from "../../i18n";

vi.mock("../../utils/exportData", () => ({ isExportMode: vi.fn(() => false) }));

describe("ExportDialog", () => {
  let hrefs: string[] = [];

  beforeEach(async () => {
    await i18n.changeLanguage("en");
    hrefs = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      hrefs.push(this.getAttribute("href") ?? "");
    });
  });

  it("names the language pop-up with its colon label, and exports in the language picked", () => {
    const onClose = vi.fn();
    render(<ExportDialog open onClose={onClose} />);
    const select = screen.getByLabelText(i18n.t("export.languageLabel")) as HTMLSelectElement;
    expect(select).toBe(screen.getByTestId("bn-export-locale-select"));
    expect(select.value).toBe("en");

    fireEvent.change(select, { target: { value: "de" } });
    fireEvent.click(screen.getByRole("button", { name: i18n.t("buttons.export") }));
    expect(hrefs).toHaveLength(1);
    expect(hrefs[0]).toContain("locale=de");
    expect(onClose).toHaveBeenCalled();
  });

  it("exports on Return, through the dialog's primary button", () => {
    render(<ExportDialog open onClose={vi.fn()} />);
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Enter" });
    expect(hrefs).toHaveLength(1);
  });
});
