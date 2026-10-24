import { describe, expect, it } from "vitest";
import {
  momentPlace,
  placeProps,
  quotesPlace,
  readContextTarget,
  sectionPlace,
  sessionPlace,
  type ContextPlace,
} from "./contextPlace";

function el(html: string): HTMLElement {
  const host = document.createElement("div");
  host.innerHTML = html;
  document.body.replaceChildren(host);
  return host;
}

function attr(place: ContextPlace | null): string {
  const v = placeProps(place)["data-bn-place"];
  return v ? ` data-bn-place='${v}'` : "";
}

const always = () => true;
const never = () => false;

describe("context places", () => {
  it("a moment carries its transcript path and its recording", () => {
    expect(momentPlace("play", "s3", 754.6, "p2")).toEqual({
      click: "play",
      verb: "show",
      dest: "transcript",
      path: "/report/sessions/s3#t-754",
      media: { key: "p2", seconds: 754.6 },
    });
  });

  it("a moment with neither a session nor a recording has no place", () => {
    expect(momentPlace("play", undefined, 12, null)).toBeNull();
  });

  it("a moment with a recording but no session can only play", () => {
    expect(momentPlace("play", undefined, 12, "p1")?.path).toBe("");
  });

  it("a session opens its transcript at the top and plays from the start", () => {
    expect(sessionPlace("navigate", "s1", true)).toMatchObject({
      verb: "open",
      path: "/report/sessions/s1",
      media: { key: "s1", seconds: 0 },
    });
    expect(sessionPlace("navigate", "s1", false).media).toBeNull();
  });

  it("no place writes no attribute", () => {
    expect(placeProps(null)).toEqual({});
  });
});

describe("readContextTarget", () => {
  it("reads the place of the link under the pointer, through its children", () => {
    const place = momentPlace("play", "s3", 754, "p2");
    const host = el(`<a${attr(place)}><span id="inner">[12:34]</span></a>`);
    const read = readContextTarget(host.querySelector("#inner"), 7, "/report/quotes/", always);
    expect(read).toEqual({ seq: 7, place, here: false, card: null, link: null });
  });

  it("says when the moment's transcript is the page showing", () => {
    const host = el(`<a id="t"${attr(momentPlace("play", "s3", 754, "s3"))}>x</a>`);
    expect(readContextTarget(host.querySelector("#t"), 1, "/report/sessions/s3", always).here).toBe(true);
    expect(readContextTarget(host.querySelector("#t"), 1, "/report/sessions/s4", always).here).toBe(false);
  });

  it("drops Play where the player has no recording for the key", () => {
    const host = el(`<a id="t"${attr(momentPlace("navigate", "s3", 754, "s3"))}>x</a>`);
    const read = readContextTarget(host.querySelector("#t"), 1, "/", never);
    expect(read.place?.media).toBeNull();
    expect(read.place?.path).toBe("/report/sessions/s3#t-754");
  });

  it("a timecode that can only play, with nothing to play, has no place", () => {
    const host = el(`<a id="t"${attr(momentPlace("play", undefined, 5, "p1"))}>x</a>`);
    expect(readContextTarget(host.querySelector("#t"), 1, "/", never).place).toBeNull();
  });

  it("a link with no place reads as none", () => {
    const host = el(`<a id="t" href="https://bristlenose.app/">x</a>`);
    expect(readContextTarget(host.querySelector("#t"), 1, "/", always).place).toBeNull();
  });

  it("tells a link into the report from one out of it", () => {
    const host = el(
      `<a id="in" href="/report/sessions/s1">a</a><a id="hash" href="#">b</a>` +
        `<a id="out" href="https://bristlenose.app/docs/">c</a><span id="none">d</span>`,
    );
    const kind = (id: string) =>
      readContextTarget(host.querySelector(`#${id}`), 1, "/", always).link;
    expect(kind("in")).toBe("internal");
    expect(kind("hash")).toBe("internal");
    expect(kind("out")).toBe("external");
    expect(kind("none")).toBeNull();
  });

  it("an unreadable place reads as none rather than throwing", () => {
    const host = el(`<a id="t" data-bn-place="{nope">x</a>`);
    expect(readContextTarget(host.querySelector("#t"), 1, "/", always).place).toBeNull();
  });

  it("a quote card under the pointer names itself, its star and its speaker link's place", () => {
    const badge = momentPlace("navigate", "s2", 30, null);
    const host = el(
      `<blockquote id="q-s2-30" class="quote-card starred">` +
        `<span id="text">words</span>` +
        `<span class="speaker"><a class="speaker-link"${attr(badge)}>p1</a></span>` +
        `</blockquote>`,
    );
    const read = readContextTarget(host.querySelector("#text"), 3, "/report/quotes/", always);
    expect(read.place).toBeNull();
    expect(read.card).toEqual({ domId: "q-s2-30", starred: true, unstar: true, count: 0, place: badge });
  });

  it("a right-click on text selected in a card is about the text, not the card", () => {
    const host = el(`<blockquote id="q1" class="quote-card"><span id="text">some words</span></blockquote>`);
    const range = document.createRange();
    range.selectNodeContents(host.querySelector("#text")!);
    window.getSelection()!.removeAllRanges();
    window.getSelection()!.addRange(range);
    expect(readContextTarget(host.querySelector("#text"), 1, "/", always).card).toBeNull();
    window.getSelection()!.removeAllRanges();
    expect(readContextTarget(host.querySelector("#text"), 1, "/", always).card?.domId).toBe("q1");
  });

  it("a blockquote with no id is not a quote card (the Discussion lens's moderator turns)", () => {
    const host = el(`<blockquote class="quote-card"><span id="text">ask</span></blockquote>`);
    expect(readContextTarget(host.querySelector("#text"), 1, "/", always).card).toBeNull();
  });

  it("carries the headings' places as written", () => {
    expect(quotesPlace("/report/quotes/#section-4")).toMatchObject({ verb: "show", dest: "quotes" });
    expect(sectionPlace("section-4", "/report/quotes/#section-4")).toMatchObject({
      verb: "go",
      anchor: "section-4",
    });
  });
});
