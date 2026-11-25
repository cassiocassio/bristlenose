import { act, fireEvent, render, screen } from "@testing-library/react";
import { useEffect } from "react";
import { MemoryRouter, useLocation } from "react-router-dom";

import badgeCss from "../../../bristlenose/theme/atoms/badge.css?raw";
import reviewCss from "../../../bristlenose/theme/molecules/threshold-review.css?raw";
import { KeylineLab } from "./KeylineLab";
import { COLOUR_SETS } from "../utils/colours";

/** The shipped theme files, loaded as the app loads them: a stylesheet in the document. */
function loadTheme(): HTMLStyleElement {
  const style = document.createElement("style");
  style.textContent = `${badgeCss}\n${reviewCss}`;
  document.head.appendChild(style);
  return style;
}

function rule(selector: string): CSSStyleRule | undefined {
  for (const sheet of Array.from(document.styleSheets)) {
    for (const r of Array.from(sheet.cssRules)) {
      if (r instanceof CSSStyleRule && r.selectorText === selector) return r;
    }
  }
  return undefined;
}

let search = "";
function Where() {
  const { search: now } = useLocation();
  useEffect(() => {
    search = now;
  }, [now]);
  return null;
}

function renderAt(url = "/report/keyline-lab") {
  return render(
    <MemoryRouter initialEntries={[url]}>
      <KeylineLab />
      <Where />
    </MemoryRouter>,
  );
}

describe("KeylineLab", () => {
  let theme: HTMLStyleElement | null = null;
  beforeEach(() => {
    // jsdom has no canvas; the lab reads contrast through one and says "no canvas" without it.
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    vi.spyOn(window, "scrollTo").mockImplementation(() => {}); // a frame scrolls its swatches up
    theme = loadTheme();
  });
  afterEach(() => {
    theme?.remove();
    vi.restoreAllMocks();
  });

  it("draws one shipped tentative Badge on every codebook fill", () => {
    renderAt();
    const slots = Object.values(COLOUR_SETS).reduce((n, s) => n + s.slots, 0);
    expect(document.querySelectorAll("[data-kl-swatch] .badge-proposed")).toHaveLength(slots);
    expect(screen.getByTestId("bn-kl-missing").hidden).toBe(true); // found every shipped rule
  });

  it("a handle retunes the shipped rule itself, writes the URL, and leaving puts the rule back", () => {
    const { unmount } = renderAt();
    const proposed = rule(".badge-proposed");
    expect(proposed?.style.getPropertyValue("opacity")).toBe("0.72");

    fireEvent.change(screen.getByTestId("bn-kl-quote-rest"), { target: { value: "0.85" } });
    expect(rule(".badge-proposed")?.style.getPropertyValue("opacity")).toBe("0.85");
    expect(JSON.parse(new URLSearchParams(search).get("k") ?? "{}").quote.rest).toBe(0.85);
    expect(screen.getByTestId("bn-kl-css").textContent).toContain("opacity: 0.85;");

    fireEvent.change(screen.getByTestId("bn-kl-quote-technique"), { target: { value: "dotted" } });
    expect(rule(".badge-proposed")?.style.getPropertyValue("border-top-style")).toBe("dotted");
    // The review row follows, linked by default.
    expect(rule(".badge.threshold-tag-tentative")?.style.getPropertyValue("border-top-style")).toBe("dotted");

    unmount();
    expect(rule(".badge-proposed")?.style.getPropertyValue("opacity")).toBe("0.72");
    expect(rule(".badge-proposed")?.style.getPropertyValue("border-top-style")).toBe("dashed");
    expect(rule(".badge.threshold-tag-tentative")?.style.getPropertyValue("border-top-style")).toBe("dashed");
  });

  it("Back to shipped clears the spec from the URL", () => {
    renderAt(`/report/keyline-lab?k=${encodeURIComponent(JSON.stringify({ quote: { rest: 0.9 } }))}`);
    expect(rule(".badge-proposed")?.style.getPropertyValue("opacity")).toBe("0.9");
    fireEvent.click(screen.getByTestId("bn-kl-reset"));
    expect(new URLSearchParams(search).has("k")).toBe(false);
    expect(rule(".badge-proposed")?.style.getPropertyValue("opacity")).toBe("0.72");
  });

  it("says so when the shipped rules are not there to retune", () => {
    theme?.remove();
    theme = null;
    renderAt();
    const warn = screen.getByTestId("bn-kl-missing");
    expect(warn.hidden).toBe(false);
    expect(warn.textContent).toContain(".badge-proposed");
  });

  it("a comparison frame follows the spec its parent posts", async () => {
    renderAt("/report/keyline-lab?frame=1&k=%7B%7D"); // a lab frame (no k is a Shipped frame, which ignores specs)
    expect(rule(".badge-proposed")?.style.getPropertyValue("opacity")).toBe("0.72");
    await act(async () => {
      window.dispatchEvent(
        new MessageEvent("message", { origin: window.location.origin, data: { type: "bn-keyline-lab", spec: { quote: { rest: 0.8 } }, pulse: "pulse" } }),
      );
    });
    expect(rule(".badge-proposed")?.style.getPropertyValue("opacity")).toBe("0.8");
    expect(document.documentElement.getAttribute("data-autocode-tentative")).toBe("pulse");
  });
});
