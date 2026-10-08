import { describe, expect, it } from "vitest";
import {
  copyTranscriptSelection,
  escapeMarkdownSpeech,
  selectedParagraphs,
  transcriptClipboard,
} from "./transcriptCopy";

// The escape's cases live in tests/fixtures/shared-format-contract.json and are
// asserted from sharedFormatContract.test.ts; this file covers the clipboard.

/** A page drawn the way TranscriptPage draws one: stamp islands, then the body. */
function page(): HTMLElement {
  const root = document.createElement("section");
  root.innerHTML = `
    <div class="transcript-segment" data-participant="m1" data-start-seconds="42">
      <span class="segment-timecode-cell" contenteditable="false">[00:42]</span>
      <span class="segment-speaker" contenteditable="false">m1</span>
      <div class="segment-body bn-sentence-start" data-position="0" lang="en"><span class="transcript-word" data-start="42">so </span><span class="transcript-word" data-start="43">which </span><span class="transcript-word" data-start="44">one?</span></div>
      <div class="segment-margin" contenteditable="false">satisfaction×</div>
    </div>
    <div class="transcript-segment" data-participant="p1" data-start-seconds="49">
      <span class="segment-timecode-cell" contenteditable="false">[00:49]</span>
      <span class="segment-speaker" contenteditable="false">p1</span>
      <div class="segment-body bn-sentence-start" data-position="1" lang="en"><span class="transcript-word" data-start="49">the </span><span class="transcript-word" data-start="50">one </span><span class="transcript-word" data-start="51">at 2*3</span></div>
    </div>
    <div class="transcript-segment" data-participant="p1" data-start-seconds="61">
      <span class="segment-timecode-cell" contenteditable="false">[01:01]</span>
      <span class="segment-speaker" contenteditable="false">p1</span>
      <div class="segment-body" data-position="2">and then it said <b>error</b></div>
    </div>`;
  document.body.appendChild(root);
  return root;
}

const words = (root: HTMLElement) => Array.from(root.querySelectorAll<HTMLElement>(".transcript-word"));
const bodies = (root: HTMLElement) => Array.from(root.querySelectorAll<HTMLElement>(".segment-body"));

describe("escapeMarkdownSpeech", () => {
  it("leaves ordinary speech alone", () => {
    expect(escapeMarkdownSpeech("[laughs] I'd say 50% — honestly, maybe #1")).toBe(
      "[laughs] I'd say 50% — honestly, maybe #1",
    );
  });
});

describe("transcriptClipboard", () => {
  it("writes the house stamp, one paragraph per block, and the same in rich text", () => {
    const { plain, html } = transcriptClipboard([
      { seconds: 42, code: "m1", text: "so which one?" },
      { seconds: 3661, code: "p1", text: "the one at 2*3 <b>" },
    ]);
    expect(plain).toBe("**`[00:42]` m1** so which one?\n\n**`[1:01:01]` p1** the one at 2\\*3 \\<b>");
    const stamp = (tc: string) =>
      '<span style="font-family:Menlo,Consolas,monospace;font-size:85%;font-weight:normal;color:#007aff">' +
      `<span style="color:#6b7280">[</span>${tc}<span style="color:#6b7280">]</span></span>`;
    expect(html).toBe(
      '<meta charset="utf-8">' +
        `<p>${stamp("00:42")} <b>m1</b> so which one?</p>` +
        `<p>${stamp("1:01:01")} <b>p1</b> the one at 2*3 &lt;b&gt;</p>`,
    );
  });
});

describe("selectedParagraphs", () => {
  it("cuts to the selected words, times a part-way start by its first word, and leaves the margin out", () => {
    const root = page();
    const range = document.createRange();
    range.setStart(words(root)[1].firstChild!, 0); // "which"
    range.setEnd(bodies(root)[2].firstChild!, 8); // "and then"
    expect(selectedParagraphs(range, root)).toEqual([
      { seconds: 43, code: "m1", text: "which one?" },
      { seconds: 49, code: "p1", text: "The one at 2*3" },
      { seconds: 61, code: "p1", text: "and then" },
    ]);
    root.remove();
  });

  it("a drag starting in the gap after a word takes the next word's time", () => {
    const root = page();
    const range = document.createRange();
    const so = words(root)[0].firstChild!; // "so "
    range.setStart(so, so.textContent!.length);
    range.setEnd(words(root)[2].firstChild!, 4);
    expect(selectedParagraphs(range, root)).toEqual([{ seconds: 43, code: "m1", text: "which one?" }]);
    root.remove();
  });

  it("draws no capital where the paragraph opens with a digit, as ::first-letter does", () => {
    const root = page();
    const body = bodies(root)[2];
    body.classList.add("bn-sentence-start");
    body.textContent = "\u201c3 people said yes";
    const range = document.createRange();
    range.selectNodeContents(body);
    expect(selectedParagraphs(range, root)?.[0].text).toBe("\u201c3 people said yes");
    body.textContent = "\u201cpeople said yes";
    range.selectNodeContents(body);
    expect(selectedParagraphs(range, root)?.[0].text).toBe("\u201cPeople said yes");
    root.remove();
  });

  it("draws the capital only where the page draws it", () => {
    const root = page();
    const range = document.createRange();
    range.selectNodeContents(bodies(root)[0]);
    expect(selectedParagraphs(range, root)?.[0].text).toBe("So which one?");
    root.remove();
  });

  it("is null when the selection holds no paragraph text", () => {
    const root = page();
    const range = document.createRange();
    range.selectNodeContents(root.querySelector(".segment-margin")!);
    expect(selectedParagraphs(range, root)).toBeNull();
    root.remove();
  });
});

describe("copyTranscriptSelection", () => {
  function copy(root: HTMLElement, range: Range) {
    const sel = window.getSelection()!;
    sel.removeAllRanges();
    sel.addRange(range);
    const data = new Map<string, string>();
    let prevented = false;
    const e = {
      clipboardData: { setData: (type: string, v: string) => data.set(type, v) },
      preventDefault: () => (prevented = true),
    } as unknown as ClipboardEvent;
    copyTranscriptSelection(e, root);
    return { data, prevented };
  }

  it("puts Markdown and rich text on the clipboard for several paragraphs", () => {
    const root = page();
    const range = document.createRange();
    range.setStart(bodies(root)[0], 0);
    range.setEnd(bodies(root)[1], bodies(root)[1].childNodes.length);
    const { data, prevented } = copy(root, range);
    expect(prevented).toBe(true);
    expect(data.get("text/plain")).toBe("**`[00:42]` m1** So which one?\n\n**`[00:49]` p1** The one at 2\\*3");
    expect(data.get("text/html")).toContain("49<span style=\"color:#6b7280\">]</span></span> <b>p1</b> The one at 2*3</p>");
    root.remove();
  });

  it("copies words inside one paragraph as plain words, unescaped", () => {
    const root = page();
    const range = document.createRange();
    range.setStart(words(root)[4].firstChild!, 0); // "one"
    range.setEnd(words(root)[5].firstChild!, 6); // "at 2*3"
    const { data } = copy(root, range);
    expect([...data.keys()]).toEqual(["text/plain"]);
    expect(data.get("text/plain")).toBe("one at 2*3");
    root.remove();
  });

  it("leaves the browser's own copy alone when no paragraph text is selected", () => {
    const root = page();
    const range = document.createRange();
    range.selectNodeContents(root.querySelector(".segment-margin")!);
    const { data, prevented } = copy(root, range);
    expect(prevented).toBe(false);
    expect(data.size).toBe(0);
    root.remove();
  });
});
