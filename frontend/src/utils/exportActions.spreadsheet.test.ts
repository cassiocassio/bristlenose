/** The spreadsheet download carries the report's language, so the sentiments are written in it
 *  as the column headings are (N177). */
import i18n from "../i18n";
import { saveQuotesSpreadsheet } from "./exportActions";

afterEach(() => vi.restoreAllMocks());

function downloadUrl(format: "csv" | "xlsx"): URL {
  let href = "";
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    href = this.href;
  });
  saveQuotesSpreadsheet(1, ["q-p1-10"], ((k: string) => k) as never, false, format);
  return new URL(href);
}

describe("saveQuotesSpreadsheet", () => {
  it.each(["csv", "xlsx"] as const)("sends the report's language on the %s download", (format) => {
    const url = downloadUrl(format);
    expect(url.pathname).toBe(`/api/projects/1/export/quotes.${format}`);
    expect(url.searchParams.get("lang")).toBe(i18n.language);
    expect(url.searchParams.get("lang")).toBeTruthy();
  });

  it("still sends the quotes and the headings", () => {
    const url = downloadUrl("csv");
    expect(url.searchParams.get("quote_ids")).toBe("q-p1-10");
    expect(url.searchParams.get("col_headers")).toContain("export.colSentiment");
  });
});
