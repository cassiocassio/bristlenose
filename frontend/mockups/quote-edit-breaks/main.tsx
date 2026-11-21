/**
 * docs/mockups/quote-edit-breaks.html — the shipped quote card beside the
 * proposal, both live. Built by docs/mockups/quote-edit-breaks.gen.py.
 *
 * Left: islands/QuoteCard.tsx itself, imported from src, as it is at the
 * commit the page was built from. Right: ProposedQuoteCard.tsx, a copy of it
 * with the proposal. The theme CSS is the whole shipped stylesheet
 * (get_default_css); the only new CSS is the PROPOSED block in the page head.
 */

import "../../src/i18n";
import { StrictMode, useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { QuoteCard } from "../../src/islands/QuoteCard";
import { setDisplayPref, useDisplayBreaks } from "../../src/contexts/DisplayPrefsStore";
import type { QuoteResponse } from "../../src/utils/types";
import { ProposedQuoteCard } from "./ProposedQuoteCard";
import { QUOTES } from "./quotes";
import { ROWS, type Row } from "./rows";

declare const BN_BUILT_FROM: string;

const NOOP = () => {};

function makeQuote(q: (typeof QUOTES)[number], side: string): QuoteResponse {
  return {
    dom_id: `${q.id}-${side}`,
    text: q.text,
    verbatim_excerpt: q.text.split(" ").slice(0, 4).join(" "),
    participant_id: q.participant,
    session_id: "s1",
    speaker_name: q.participant,
    start_timecode: q.start,
    end_timecode: q.start + 30,
    sentiment: "frustration",
    intensity: 2,
    researcher_context: null,
    quote_type: "screen_specific",
    topic_label: "Checkout",
    is_starred: false,
    is_hidden: false,
    edited_text: null,
    tags: [],
    deleted_badges: [],
    proposed_tags: [],
    segment_index: 3,
  };
}

const COMMON = {
  isStarred: false,
  isHidden: false,
  userTags: [{ name: "delivery cost", codebook_group: "Checkout", colour_set: "ux", colour_index: 1 }],
  allTagNames: ["delivery cost"],
  deletedBadges: [] as string[],
  tagVocabulary: [] as string[],
  sessionId: "s1",
  hasMedia: false,
  hasModerator: false,
  proposedTags: [],
  flashingTags: new Set<string>(),
  moderatorQuestion: null,
  isQuestionOpen: false,
  isPillVisible: false,
  onToggleStar: NOOP,
  onToggleHide: NOOP,
  onTagAdd: NOOP,
  onTagRemove: NOOP,
  onBadgeDelete: NOOP,
  onBadgeRestore: NOOP,
  onProposedAccept: NOOP,
  onProposedDeny: NOOP,
  onToggleQuestion: NOOP,
  onQuoteHoverEnter: NOOP,
  onQuoteHoverLeave: NOOP,
  onPillHoverEnter: NOOP,
  onPillHoverLeave: NOOP,
};

// ── Key echo: what you pressed, and what state the card is in after ─────

function keyName(e: KeyboardEvent): string | null {
  const k = e.key;
  if (["Shift", "Alt", "Meta", "Control"].includes(k)) return null;
  const mods = [e.metaKey && "⌘", e.ctrlKey && "Ctrl", e.altKey && "Option", e.shiftKey && "Shift"].filter(Boolean);
  const name = k === "Enter" ? "Return" : k === " " ? "Space" : k.length === 1 ? null : k;
  if (name === null && mods.length === 0) return null; // ordinary typing
  return [...mods, name ?? k.toUpperCase()].join("-");
}

function cardState(col: HTMLElement | null): string {
  const card = col?.querySelector("blockquote.quote-card");
  if (!card?.classList.contains("editing")) return "rest";
  return card.querySelector(".crop-word.included") ? "trim" : "text editing";
}

interface Log {
  t: number;
  text: string;
  kind: "key" | "write" | "note";
}

function useLog() {
  const [log, setLog] = useState<Log[]>([]);
  const add = useCallback((text: string, kind: Log["kind"]) => {
    setLog((l) => [{ t: Date.now(), text, kind }, ...l].slice(0, 14));
  }, []);
  return { log, add, clear: () => setLog([]) };
}

function LogView({ log }: { log: Log[] }) {
  return (
    <ol className="mk-log" aria-live="polite">
      {log.length === 0 && <li className="mk-log-empty">Click the quote and press keys.</li>}
      {log.map((l) => (
        <li key={l.t + l.text} className={`mk-log-${l.kind}`}>
          {l.text}
        </li>
      ))}
    </ol>
  );
}

function RowsTable({ side }: { side: "shipped" | "proposed" }) {
  let group = "";
  return (
    <table className="mk-rows">
      <tbody>
        {ROWS.map((r: Row, i) => {
          const head = r.group !== group ? ((group = r.group), r.group) : null;
          const same = r.proposed === "same";
          const text = side === "shipped" ? r.shipped : same ? r.shipped : r.proposed;
          return [
            head && (
              <tr key={`h${i}`} className="mk-rows-group">
                <th colSpan={2}>{head}</th>
              </tr>
            ),
            <tr key={i} className={same ? "mk-same" : "mk-diff"}>
              <th scope="row">
                <kbd>{r.key}</kbd>
              </th>
              <td>
                {text}
                {same && <span className="mk-tag">same</span>}
                {r.open && side === "proposed" && <span className="mk-tag mk-tag-open">your call</span>}
              </td>
            </tr>,
          ];
        })}
      </tbody>
    </table>
  );
}

// ── The page ───────────────────────────────────────────────────────────

function App() {
  const [qi, setQi] = useState(0);
  const q = QUOTES[qi];
  const breaks = useDisplayBreaks();
  const [width, setWidth] = useState(620);
  const [tabStays, setTabStays] = useState(false);
  const [whenOff, setWhenOff] = useState(true);

  // Shipped: the words only. Proposed: the words and the researcher's breaks.
  const [shippedText, setShippedText] = useState<string>(q.text);
  const [propText, setPropText] = useState<string>(q.text);
  const [propBreaks, setPropBreaks] = useState<number[] | null>(null);
  const [gen, setGen] = useState(0); // remount both cards on reset
  const shippedLog = useLog();
  const propLog = useLog();
  const shippedCol = useRef<HTMLDivElement>(null);
  const propCol = useRef<HTMLDivElement>(null);

  const reset = useCallback(
    (i = qi) => {
      setQi(i);
      setShippedText(QUOTES[i].text);
      setPropText(QUOTES[i].text);
      setPropBreaks(null);
      setGen((g) => g + 1);
      shippedLog.clear();
      propLog.clear();
    },
    [qi],
  );

  // Echo keys in each column, with the state the card is in afterwards.
  useEffect(() => {
    const pairs: Array<[HTMLDivElement | null, ReturnType<typeof useLog>["add"]]> = [
      [shippedCol.current, shippedLog.add],
      [propCol.current, propLog.add],
    ];
    const offs = pairs.map(([col, add]) => {
      if (!col) return () => {};
      const on = (e: KeyboardEvent) => {
        const k = keyName(e);
        if (!k) return;
        requestAnimationFrame(() => requestAnimationFrame(() => add(`${k}  ·  now: ${cardState(col)}`, "key")));
      };
      col.addEventListener("keydown", on, true);
      return () => col.removeEventListener("keydown", on, true);
    });
    return () => offs.forEach((f) => f());
  }, [shippedLog.add, propLog.add]);

  const words = (t: string) => t.split(/\s+/).filter(Boolean);
  const short = (t: string) => {
    const w = words(t);
    return w.length > 12 ? `${w.slice(0, 5).join(" ")} … ${w.slice(-4).join(" ")}` : t;
  };

  return (
    <>
      <header className="mk-bar">
        <strong>Quote editing with paragraphs</strong>
        <span className="mk-built">built from {BN_BUILT_FROM}</span>
        <label>
          Quote{" "}
          <select value={qi} onChange={(e) => reset(Number(e.target.value))}>
            {QUOTES.map((x, i) => (
              <option key={x.id} value={i}>
                {x.participant} · {words(x.text).length} words
              </option>
            ))}
          </select>
        </label>
        <label>
          Card width{" "}
          <input type="range" min={340} max={900} step={10} value={width} onChange={(e) => setWidth(Number(e.target.value))} />{" "}
          <span className="mk-num">{width}px</span>
        </label>
        <label>
          <input type="checkbox" checked={breaks === "on"} onChange={(e) => setDisplayPref("breaks", e.target.checked ? "on" : "off")} />{" "}
          Break long paragraphs
        </label>
        <button type="button" onClick={() => reset()}>
          Reset both
        </button>
        <span className="mk-sep" />
        <Toggles />
        <span className="mk-sep" />
        <span className="mk-label">Proposal, open decisions:</span>
        <label>
          <input type="checkbox" checked={whenOff} onChange={(e) => setWhenOff(e.target.checked)} /> Your paragraphs show with Break off
        </label>
        <label>
          <input type="checkbox" checked={tabStays} onChange={(e) => setTabStays(e.target.checked)} /> Tab leaves focus on the card
        </label>
      </header>

      <p className="mk-key">
        <span className="mk-key-artefact">Real pixels</span> the two cards, drawn by the shipped stylesheet ·{" "}
        <span className="mk-key-comment">Commentary</span> everything with a hatched edge
      </p>

      <main className="mk-cols">
        {(["shipped", "proposed"] as const).map((side) => {
          const isShipped = side === "shipped";
          const log = isShipped ? shippedLog : propLog;
          const text = isShipped ? shippedText : propText;
          const quote = makeQuote(q, side);
          return (
            <section key={side} className="mk-col" ref={isShipped ? shippedCol : propCol}>
              <div className="mk-frame">
                <div className="mk-frame-bar">
                  {isShipped ? "Shipped · islands/QuoteCard.tsx" : "Proposed · mockups/quote-edit-breaks/ProposedQuoteCard.tsx"}
                </div>
                <div className={`mk-stage${isShipped ? "" : " bn-proposed"}`}>
                  <section>
                    <div className="quote-group" style={{ width }}>
                      {isShipped ? (
                        <QuoteCard
                          key={`s${gen}`}
                          {...COMMON}
                          quote={quote}
                          displayText={text}
                          isEdited={text !== q.text}
                          onEditCommit={(_id, t) => {
                            setShippedText(t);
                            log.add(t === q.text ? "→ revert: the quote edit is deleted" : `→ saved QuoteEdit · text = “${short(t)}”`, "write");
                          }}
                        />
                      ) : (
                        <ProposedQuoteCard
                          key={`p${gen}`}
                          {...COMMON}
                          quote={quote}
                          displayText={text}
                          isEdited={text !== q.text || propBreaks !== null}
                          researcherBreaks={propBreaks}
                          researcherBreaksWhenOff={whenOff}
                          tabStaysOnCard={tabStays}
                          onKeyEcho={(w) => log.add(w, "note")}
                          onEditCommit={(_id, t) => {
                            setPropText(t);
                            if (t === q.text) {
                              setPropBreaks(null);
                              log.add("→ revert: the quote edit and your paragraphs are deleted", "write");
                            } else log.add(`→ saved QuoteEdit · text = “${short(t)}”`, "write");
                          }}
                          onBreaksCommit={(_id, b) => {
                            setPropBreaks(b);
                            if (b === null) log.add("→ deleted quote_breaks: back to automatic paragraphs", "write");
                            else
                              log.add(
                                `→ saved quote_breaks · source = researcher · ${b.length === 0 ? "no breaks" : `breaks after words ${b.map((x) => x + 1).join(", ")}`}`,
                                "write",
                              );
                          }}
                        />
                      )}
                    </div>
                  </section>
                </div>
              </div>
              <div className="mk-comment">
                <h3>What happened</h3>
                <LogView log={log.log} />
                <h3>Every key and gesture{isShipped ? ", as shipped" : ", proposed"}</h3>
                <RowsTable side={side} />
              </div>
            </section>
          );
        })}
      </main>
    </>
  );
}

/** Palette, appearance and platform, as the app sets them on <html>. */
function Toggles() {
  const root = document.documentElement;
  const [pal, setPal] = useState(root.dataset.colorTheme ?? "default");
  const [scheme, setScheme] = useState(root.dataset.theme ?? "auto");
  const [plat, setPlat] = useState(root.dataset.platform === "desktop" ? "mac" : "web");
  useEffect(() => {
    root.dataset.colorTheme = pal;
  }, [pal, root]);
  useEffect(() => {
    if (scheme === "auto") delete root.dataset.theme;
    else root.dataset.theme = scheme;
  }, [scheme, root]);
  useEffect(() => {
    if (plat === "mac") root.dataset.platform = "desktop";
    else delete root.dataset.platform;
  }, [plat, root]);
  return (
    <>
      <label>
        Type{" "}
        <select value={plat} onChange={(e) => setPlat(e.target.value)}>
          <option value="mac">Mac app (SF Pro)</option>
          <option value="web">Browser (Inter)</option>
        </select>
      </label>
      <label>
        Palette{" "}
        <select value={pal} onChange={(e) => setPal(e.target.value)}>
          <option value="edo">Edo</option>
          <option value="default">Default</option>
        </select>
      </label>
      <label>
        Appearance{" "}
        <select value={scheme} onChange={(e) => setScheme(e.target.value)}>
          <option value="auto">Auto</option>
          <option value="light">Light</option>
          <option value="dark">Dark</option>
        </select>
      </label>
    </>
  );
}

// The Mac app's defaults on a Mac (SF Pro, Edo); the browser's elsewhere.
// Set after i18n has loaded, so it does not go looking for the app's own strings.
if (/Mac/.test(navigator.platform)) {
  document.documentElement.dataset.platform = "desktop";
  document.documentElement.dataset.colorTheme = "edo";
} else {
  document.documentElement.dataset.colorTheme = "default";
}
setDisplayPref("breaks", "on");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
