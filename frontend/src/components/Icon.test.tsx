import { render } from "@testing-library/react";
import { Icon } from "./Icon";

describe("Icon", () => {
  it("is hidden from assistive technology when decorative", () => {
    const { container } = render(<Icon name="close" decorative />);
    const svg = container.querySelector("svg")!;
    expect(svg.getAttribute("aria-hidden")).toBe("true");
    expect(svg.getAttribute("role")).toBeNull();
  });

  it("becomes the accessible name when labelled", () => {
    const { getByRole } = render(<Icon name="close" label="Close" />);
    const img = getByRole("img", { name: "Close" });
    expect(img.getAttribute("aria-hidden")).toBeNull();
  });

  it("carries the house classes, so CSS and tests can find a concept", () => {
    const { container } = render(<Icon name="check" size="menu" decorative className="extra" />);
    const cls = container.querySelector("svg")!.getAttribute("class")!.split(" ");
    expect(cls).toEqual(expect.arrayContaining(["bn-icon", "bn-icon-check", "bn-icon--menu", "extra"]));
  });

  it("holds the stroke in screen pixels on every path (the stem rule needs it)", () => {
    const { container } = render(<Icon name="close" decorative />);
    const parts = container.querySelectorAll("svg > *");
    expect(parts.length).toBeGreaterThan(0);
    parts.forEach((p) => expect(p.getAttribute("vector-effect")).toBe("non-scaling-stroke"));
  });

  it("draws Lucide's paths, not an improvised one", () => {
    const { container } = render(<Icon name="close" decorative />);
    const ds = [...container.querySelectorAll("path")].map((p) => p.getAttribute("d"));
    expect(ds).toEqual(["M18 6 6 18", "m6 6 12 12"]);
  });

  it("refuses, at compile time, an icon that is neither labelled nor decorative", () => {
    // @ts-expect-error — one of `label` or `decorative` is required
    const bare = <Icon name="close" />;
    // @ts-expect-error — and not both
    const both = <Icon name="close" label="Close" decorative />;
    expect(bare && both).toBeTruthy();
  });
});

describe("Icon fallback", () => {
  it("carries a house-weight stroke attribute for projects whose baked CSS predates the stem rule", () => {
    const { container } = render(<Icon name="close" decorative />);
    expect(container.querySelector("svg")!.getAttribute("stroke-width")).toBe("1.25");
  });
});
