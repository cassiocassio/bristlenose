/**
 * The Screens lens (diagnostics): every screen the participants were on, a large screengrab of
 * each, and the quotes said there floating beside it, pinned to the on-screen line they read.
 *
 * docs/design-screens.md S5. Data from GET /screens (server/routes/screens.py), stills from
 * GET /screens/still. Quotes are the report's own: the lens joins the screens' DOM ids to the
 * quotes store, so star, hide and tags here are the same gestures as on the Quotes lens.
 *
 * Diagnostics-only and English-only while it is rough (the Specimen precedent): reached from the
 * Diagnostics menu on the Mac and from a nav link with diagnostics on in the browser.
 */

import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Badge } from "../../components/Badge";
import { Counter, type CounterItem } from "../../components/Counter";
import { PersonBadge } from "../../components/PersonBadge";
import { TagInput, type TagVocabularyGroup } from "../../components/TagInput";
import { Toggle } from "../../components/Toggle";
import {
  addTagToQuotes,
  hideQuotes,
  initFromQuotes,
  removeTag,
  toggleStar,
  unhideQuotes,
  useQuotesStore,
} from "../../contexts/QuotesContext";
import { apiGet, getCodebook } from "../../utils/api";
import { getTagBg } from "../../utils/colours";
import { formatTimecode } from "../../utils/format";
import type { QuoteResponse, QuotesListResponse, TagResponse } from "../../utils/types";
import {
  clearSpots,
  leaderPath,
  placeColumn,
  putSpot,
  sideFor,
  spotsFor,
  stillKey,
  topZ,
  WIDE_STAGE,
  type Side,
  type Spot,
} from "./layout";
import "./screens.css";

// ── Types ────────────────────────────────────────────────────────────────

interface Pin {
  dom_id: string;
  box: [number, number, number, number];
  phrase: string;
  line: string;
}

interface ScreenTab {
  session_id: string;
  code: string;
  t: number;
  crop: [number, number, number, number];
  heading: string;
  visits: [number, number][];
  pins: Pin[];
  loose: string[];
}

interface Screen {
  key: string;
  name: string;
  quotes: number;
  tabs: ScreenTab[];
}

interface ScreensResponse {
  enabled: boolean;
  unavailable: string | null;
  pending: boolean;
  reading: string | null;
  videos: number;
  indexed: number;
  /** Why a recording has no index, by session id (older servers omit it). */
  failed?: Record<string, string>;
  /** Recordings the engine read and found no text in. */
  blank?: string[];
  screens: Screen[];
}

/** Still reading: the job is running, or recordings remain that have neither an index nor a failure. */
function stillReading(r: ScreensResponse): boolean {
  return r.pending || r.indexed + Object.keys(r.failed ?? {}).length < r.videos;
}

/** What the lens says about recordings it could not, or has not yet, read. */
function readingNote(r: ScreensResponse): string[] {
  const out: string[] = [];
  if (stillReading(r)) {
    out.push(
      r.pending
        ? `Reading screens… ${r.indexed} of ${r.videos} recordings${r.reading ? ` (now ${r.reading})` : ""}.`
        : `Waiting to read ${r.videos - r.indexed} of ${r.videos} recordings (after the current analysis).`,
    );
  }
  for (const [sid, why] of Object.entries(r.failed ?? {})) out.push(`Couldn’t read ${sid}: ${why}.`);
  for (const sid of r.blank ?? []) out.push(`No text found in ${sid}’s recording.`);
  return out;
}

type Front = "hover" | "click";
type StackStyle = "straight" | "diagonal";

// ── Stills ───────────────────────────────────────────────────────────────

const stills = new Map<string, string>();
const stillErrors = new Map<string, string>();
const stillWaiters = new Map<string, Promise<string | null>>();

function stillUrl(tab: ScreenTab, w: number): string {
  const crop = tab.crop.map((v) => v.toFixed(4)).join(",");
  return `/screens/still?session_id=${encodeURIComponent(tab.session_id)}&t=${tab.t}&w=${w}&crop=${crop}`;
}

/** The still's data URI, or why there is none (null while it loads). */
function useStill(tab: ScreenTab | undefined, w: number): { src: string | null; error: string | null } {
  const url = tab ? stillUrl(tab, w) : "";
  const [fetched, setFetched] = useState<{ url: string; src: string | null } | null>(null);
  useEffect(() => {
    if (!url || stills.has(url)) return;
    let live = true;
    let p = stillWaiters.get(url);
    if (!p) {
      p = apiGet<{ src: string }>(url)
        .then((r) => {
          stills.set(url, r.src);
          return r.src;
        })
        .catch((e: Error) => {
          // Shown in place of the screengrab: a missing still must not look like one still loading.
          stillErrors.set(url, e.message || "no still");
          console.warn("Screens: no still for", url, e);
          return null;
        })
        .finally(() => stillWaiters.delete(url));
      stillWaiters.set(url, p);
    }
    p.then((s) => {
      if (live) setFetched({ url, src: s });
    });
    return () => {
      live = false;
    };
  }, [url]);
  if (!url) return { src: null, error: null };
  const src = stills.get(url) ?? (fetched?.url === url ? fetched.src : null);
  return { src, error: src ? null : (stillErrors.get(url) ?? null) };
}

// ── Preferences (try both, the prototype's question) ─────────────────────

function readPref<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key);
    return v && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
  } catch {
    return fallback;
  }
}

function writePref(key: string, v: string): void {
  try {
    localStorage.setItem(key, v);
  } catch {
    /* the choice lasts the page */
  }
}

// ── Text ─────────────────────────────────────────────────────────────────

/** The words read aloud, marked where they appear in the quote. */
function marked(text: string, phrase: string): React.ReactNode {
  const words = phrase.split(" ").filter(Boolean);
  if (!words.length) return text;
  const esc = (w: string) => w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const re = new RegExp(words.map(esc).join("[^\\p{L}\\p{N}]+"), "iu");
  const m = re.exec(text);
  if (!m) return text;
  return (
    <>
      {text.slice(0, m.index)}
      <mark className="screens-read">{m[0]}</mark>
      {text.slice(m.index + m[0].length)}
    </>
  );
}

const HIDE_ICON = (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94" />
    <path d="M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19" />
    <line x1="1" y1="1" x2="23" y2="23" />
  </svg>
);

// ── A card ───────────────────────────────────────────────────────────────

interface TagInfo {
  group: string;
  colour_set: string;
  colour_index: number;
}

interface CardProps {
  quote: QuoteResponse;
  phrase: string;
  text: string;
  starred: boolean;
  tags: TagResponse[];
  focused: boolean;
  dragging: boolean;
  vocabulary: string[];
  groupedVocabulary: TagVocabularyGroup[];
  tagInfo: Record<string, TagInfo>;
  style?: React.CSSProperties;
  pin?: string;
  register?: (el: HTMLElement | null) => void;
  onEnter: () => void;
  onLeave: () => void;
  onClick: (e: React.MouseEvent) => void;
  onGrip: (e: React.PointerEvent) => void;
}

function ScreenCard({ register, ...p }: CardProps) {
  const { t } = useTranslation();
  const [tagging, setTagging] = useState(false);
  const q = p.quote;
  const commitTag = (name: string) => {
    const info = p.tagInfo[name.toLowerCase()];
    addTagToQuotes([q.dom_id], {
      name,
      codebook_group: info?.group ?? "Uncategorised",
      colour_set: info?.colour_set ?? "",
      colour_index: info?.colour_index ?? 0,
      source: "human",
    });
  };
  const cls = ["quote-card", p.starred && "starred", p.focused && "bn-focused", p.dragging && "is-dragging"]
    .filter(Boolean)
    .join(" ");
  return (
    // Bringing a card forward is a pointer affordance (hover, or click in click mode); every
    // control inside the card — star, hide, tag — is a real button reachable by keyboard.
    // eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-noninteractive-element-interactions
    <blockquote
      ref={register}
      className={cls}
      style={p.style}
      data-dom={q.dom_id}
      data-pin={p.pin}
      onMouseEnter={p.onEnter}
      onMouseLeave={p.onLeave}
      onClick={p.onClick}
    >
      <span className="screens-grip screens-grip-top" aria-hidden="true" onPointerDown={p.onGrip} />
      <span className="screens-grip screens-grip-side" aria-hidden="true" onPointerDown={p.onGrip} />
      <div className="quote-row">
        <span className="timecode">[{formatTimecode(q.start_timecode)}]</span>
        <div className="quote-body">
          <span className="quote-text-wrapper">
            <span className="smart-quote">{"“"}</span>
            {marked(p.text, p.phrase)}
            <span className="smart-quote">{"”"}</span>
          </span>{" "}
          <span className="speaker">
            <PersonBadge
              code={q.participant_id}
              role="participant"
              name={q.speaker_name !== q.participant_id ? q.speaker_name : undefined}
            />
          </span>
          <div className="badges">
            {q.sentiment && <Badge text={q.sentiment} variant="ai" sentiment={q.sentiment} />}
            {p.tags.map((tag) => (
              <Badge
                key={tag.name}
                text={tag.name}
                variant="user"
                colour={tag.colour_set ? getTagBg(tag.colour_set, tag.colour_index) : undefined}
                onDelete={() => removeTag(q.dom_id, tag.name)}
              />
            ))}
            {tagging ? (
              <TagInput
                vocabulary={p.vocabulary}
                groupedVocabulary={p.groupedVocabulary}
                exclude={p.tags.map((tg) => tg.name)}
                onCommit={(name) => {
                  commitTag(name);
                  setTagging(false);
                }}
                onCommitAndReopen={(name) => commitTag(name)}
                onCancel={() => setTagging(false)}
              />
            ) : (
              <span
                className="badge badge-add"
                role="button"
                tabIndex={0}
                aria-label={t("quotes.addTag")}
                onClick={(e) => {
                  e.stopPropagation();
                  setTagging(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    setTagging(true);
                  }
                }}
              >
                +
              </span>
            )}
          </div>
        </div>
      </div>
      <Toggle
        active={false}
        onToggle={() => hideQuotes([q.dom_id])}
        className="hide-btn"
        aria-label={t("quotes.hideQuote")}
      >
        {HIDE_ICON}
      </Toggle>
      <Toggle
        active={p.starred}
        onToggle={(on) => toggleStar(q.dom_id, on)}
        className="star-btn"
        activeClassName="starred"
        aria-label={t("quotes.starQuote")}
      >
        &#9733;
      </Toggle>
    </blockquote>
  );
}

// ── The lens ─────────────────────────────────────────────────────────────

export function ScreensLens() {
  const [data, setData] = useState<ScreensResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [cur, setCur] = useState(0);
  const [tab, setTab] = useState(0);
  const [front, setFront] = useState<Front>(() => readPref("bristlenose-screens-front", ["hover", "click"] as const, "hover"));
  const [stack, setStack] = useState<StackStyle>(() =>
    readPref("bristlenose-screens-stack", ["straight", "diagonal"] as const, "straight"),
  );
  const [vocabulary, setVocabulary] = useState<string[]>([]);
  const [groupedVocabulary, setGroupedVocabulary] = useState<TagVocabularyGroup[]>([]);
  const [tagInfo, setTagInfo] = useState<Record<string, TagInfo>>({});
  const store = useQuotesStore();

  // Screens: poll while the job is still reading recordings.
  useEffect(() => {
    let live = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const load = () => {
      apiGet<ScreensResponse>("/screens")
        .then((r) => {
          if (!live) return;
          setData(r);
          if (r.enabled && !r.unavailable && stillReading(r)) timer = setTimeout(load, 5000);
        })
        .catch((e: Error) => live && setError(e.message));
    };
    load();
    return () => {
      live = false;
      if (timer) clearTimeout(timer);
    };
  }, []);

  // Quotes: the report's own store, hydrated as the Quotes lens hydrates it.
  useEffect(() => {
    apiGet<QuotesListResponse>("/quotes")
      .then((json) => {
        const all = [
          ...json.sections.flatMap((s) => s.quotes),
          ...json.themes.flatMap((th) => th.quotes),
          ...(json.unjoined ?? []),
        ];
        initFromQuotes(all, false, json.uncategorised);
      })
      // Without the quotes every screen would read "0 quotes": say so instead.
      .catch((e: Error) => setError(`couldn’t load the quotes (${e.message})`));
    getCodebook()
      .then((cb) => {
        setVocabulary(cb.all_tag_names);
        const info: Record<string, TagInfo> = {};
        const groups: TagVocabularyGroup[] = [];
        for (const g of cb.groups) {
          const tags: { name: string; colourIndex: number }[] = [];
          for (const tg of g.tags) {
            info[tg.name.toLowerCase()] = { group: g.name, colour_set: g.colour_set, colour_index: tg.colour_index };
            tags.push({ name: tg.name, colourIndex: tg.colour_index });
          }
          groups.push({ groupName: g.name, colourSet: g.colour_set, tags });
        }
        setTagInfo(info);
        setGroupedVocabulary(groups);
      })
      .catch((e: Error) => console.warn("Screens: no codebook, so no tag vocabulary", e));
  }, []);

  const byId = useMemo(() => {
    const m = new Map<string, QuoteResponse>();
    for (const q of [...store.quotes, ...(store.uncategorised ?? [])]) m.set(q.dom_id, q);
    return m;
  }, [store.quotes, store.uncategorised]);

  const screens = data?.screens ?? [];
  const screen = screens[Math.min(cur, Math.max(0, screens.length - 1))];
  const tabIdx = screen ? Math.min(tab, screen.tabs.length - 1) : 0;

  const go = useCallback(
    (i: number, j = 0) => {
      if (!screens.length) return;
      setCur(((i % screens.length) + screens.length) % screens.length);
      setTab(j);
    },
    [screens.length],
  );

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const el = e.target;
      if (el instanceof HTMLElement && (el.closest("input, textarea, select, [contenteditable='true']") || el.isContentEditable)) return;
      if (!screen) return;
      if (e.key === "ArrowDown") go(cur + 1);
      else if (e.key === "ArrowUp") go(cur - 1);
      else if (e.key === "ArrowRight" && screen.tabs.length > 1) go(cur, (tabIdx + 1) % screen.tabs.length);
      else if (e.key === "ArrowLeft" && screen.tabs.length > 1)
        go(cur, (tabIdx - 1 + screen.tabs.length) % screen.tabs.length);
      else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [go, cur, tabIdx, screen]);

  if (error) return <div className="screens-lens-status">Screens: {error}</div>;
  if (!data) return <div className="screens-lens-status">Reading screens…</div>;
  if (!data.enabled) {
    return <div className="screens-lens-status">Screens are off. Turn on Diagnostics to read shared screens.</div>;
  }
  if (data.unavailable) return <div className="screens-lens-status">Screens can’t be read here: {data.unavailable}</div>;
  if (!data.videos) return <div className="screens-lens-status">No recordings with video in this project.</div>;
  if (!screens.length) {
    return (
      <div className="screens-lens-status">
        {readingNote(data).map((line) => (
          <p key={line}>{line}</p>
        ))}
        {!stillReading(data) && data.indexed > (data.blank ?? []).length && (
          <p>No screens found: these recordings show no web page with an address or tab title.</p>
        )}
      </div>
    );
  }
  return (
    <div className="screens-lens">
      <ScreenNav screens={screens} cur={cur} onPick={(i) => go(i)} byId={byId} />
      <main className="screens-main">
        <div className="screens-controls">
          <label>
            Bring a quote forward on{" "}
            <select
              value={front}
              onChange={(e) => {
                const v = e.target.value as Front;
                setFront(v);
                writePref("bristlenose-screens-front", v);
              }}
            >
              <option value="hover">hover</option>
              <option value="click">click</option>
            </select>
          </label>
          <label>
            Stacks{" "}
            <select
              value={stack}
              onChange={(e) => {
                const v = e.target.value as StackStyle;
                setStack(v);
                writePref("bristlenose-screens-stack", v);
              }}
            >
              <option value="straight">straight</option>
              <option value="diagonal">diagonal</option>
            </select>
          </label>
          {readingNote(data).map((line) => (
            <span key={line}>{line}</span>
          ))}
        </div>
        {screen && (
          <ScreenBoard
            key={`${screen.key}|${tabIdx}`}
            screen={screen}
            tabIdx={tabIdx}
            onTab={(j) => go(cur, j)}
            byId={byId}
            store={store}
            front={front}
            stack={stack}
            vocabulary={vocabulary}
            groupedVocabulary={groupedVocabulary}
            tagInfo={tagInfo}
          />
        )}
      </main>
    </div>
  );
}

// ── Navigation ───────────────────────────────────────────────────────────

function NavThumb({ tab }: { tab: ScreenTab }) {
  const { src, error } = useStill(tab, 240);
  return src ? <img alt="" src={src} /> : <span className="screens-thumb-empty" title={error ?? undefined} />;
}

function screenTitle(screen: Screen, tab?: ScreenTab): string {
  if (!screen.name.startsWith("/")) return screen.name.charAt(0).toUpperCase() + screen.name.slice(1);
  if (tab?.heading) return tab.heading;
  const hs = [...new Set(screen.tabs.map((t) => t.heading).filter(Boolean))];
  return hs.join(" · ") || screen.name;
}

function ScreenNav({
  screens,
  cur,
  onPick,
  byId,
}: {
  screens: Screen[];
  cur: number;
  onPick: (i: number) => void;
  byId: Map<string, QuoteResponse>;
}) {
  const listRef = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const el = listRef.current?.querySelector<HTMLElement>('[aria-current="true"]');
    if (el && typeof el.scrollIntoView === "function") el.scrollIntoView({ block: "nearest" });
  }, [cur]);
  const participants = new Set(screens.flatMap((s) => s.tabs.map((t) => t.code))).size;
  return (
    <nav className="screens-nav" aria-label="Screens">
      <div className="screens-nav-head">
        {screens.length} {screens.length === 1 ? "screen" : "screens"} · {participants}{" "}
        {participants === 1 ? "participant" : "participants"}
      </div>
      <ol ref={listRef}>
        {screens.map((s, i) => {
          const codes = [...new Set(s.tabs.map((t) => t.code))];
          const said = s.tabs.reduce(
            (n, t) => n + [...t.pins.map((p) => p.dom_id), ...t.loose].filter((d) => byId.has(d)).length,
            0,
          );
          return (
            <li key={s.key}>
              <a
                href={`#${s.key}`}
                aria-current={i === cur ? "true" : "false"}
                onClick={(e) => {
                  e.preventDefault();
                  onPick(i);
                }}
              >
                <span className={`screens-thumb${s.tabs.length > 1 ? " stacked" : ""}`}>
                  {s.tabs.slice(0, 3).map((t) => (
                    <NavThumb key={`${t.session_id}@${t.t}`} tab={t} />
                  ))}
                </span>
                <span>
                  <span className="screens-nav-title">{screenTitle(s)}</span>
                  {s.name.startsWith("/") && <span className="screens-nav-path">{s.name}</span>}
                  <span className="screens-nav-meta">
                    <span className="screens-count">{said}</span>
                    <span className="screens-codes">
                      {codes.slice(0, 12).map((c) => (
                        <span key={c} className="bn-speaker-badge-code">
                          {c}
                        </span>
                      ))}
                      {codes.length > 12 && <span className="screens-more">+{codes.length - 12}</span>}
                    </span>
                  </span>
                </span>
              </a>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

// ── The board ────────────────────────────────────────────────────────────

interface BoardProps {
  screen: Screen;
  tabIdx: number;
  onTab: (j: number) => void;
  byId: Map<string, QuoteResponse>;
  store: ReturnType<typeof useQuotesStore>;
  front: Front;
  stack: StackStyle;
  vocabulary: string[];
  groupedVocabulary: TagVocabularyGroup[];
  tagInfo: Record<string, TagInfo>;
}

interface Geometry {
  stageW: number;
  W: number;
  H: number;
  sx: number;
  sy: number;
  colW: number;
}

interface Drag {
  dom: string;
  left: number;
  top: number;
  width: number;
  z: number;
}

function ScreenBoard(props: BoardProps) {
  const { screen, tabIdx, byId, store } = props;
  const tab = screen.tabs[tabIdx];
  const still = stillKey(tab.session_id, tab.t);
  const { src, error: stillError } = useStill(tab, 1600);
  const stageRef = useRef<HTMLDivElement>(null);
  const boardRef = useRef<HTMLDivElement>(null);
  const shotRef = useRef<HTMLDivElement>(null);
  const cardEls = useRef(new Map<string, HTMLElement>());
  const [geo, setGeo] = useState<Geometry | null>(null);
  const [tops, setTops] = useState<Record<string, { top: number; slide: number; z: number }>>({});
  const [stacked, setStacked] = useState<Record<Side, boolean>>({ L: false, R: false });
  const [colH, setColH] = useState(0);
  const [leaders, setLeaders] = useState<{ id: string; d: string; end: [number, number] }[]>([]);
  const [focused, setFocused] = useState<string | null>(null);
  const [drag, setDrag] = useState<Drag | null>(null);
  const [spots, setSpots] = useState<Record<string, Spot>>(() => spotsFor(still));
  const [hiddenOpen, setHiddenOpen] = useState(false);

  const visible = (dom: string) => byId.has(dom) && !store.hidden[dom];
  const pins = tab.pins.filter((p) => visible(p.dom_id));
  const pinByDom = new Map(pins.map((p) => [p.dom_id, p]));
  // Everything else said on this screen, by every participant on it.
  const shownPins = new Set(pins.map((p) => p.dom_id));
  const rest = screen.tabs
    .flatMap((t) => [...t.pins.map((p) => p.dom_id), ...t.loose])
    .filter((d, i, a) => a.indexOf(d) === i && !shownPins.has(d) && visible(d))
    .sort((a, b) => (byId.get(a)!.start_timecode - byId.get(b)!.start_timecode));
  const free = new Set(Object.keys(spots).filter((d) => visible(d)));
  const hiddenHere = screen.tabs
    .flatMap((t) => [...t.pins.map((p) => p.dom_id), ...t.loose])
    .filter((d, i, a) => a.indexOf(d) === i && byId.has(d) && store.hidden[d]);

  // Measure the stage and the screengrab.
  useLayoutEffect(() => {
    const measure = () => {
      const stage = stageRef.current, shot = shotRef.current, board = boardRef.current;
      if (!stage || !shot || !board) return;
      const img = shot.querySelector("img");
      const W = img?.clientWidth ?? shot.clientWidth;
      const H = img?.clientHeight ?? 0;
      const col = board.querySelector<HTMLElement>(".screens-col-r");
      const g = { stageW: stage.clientWidth, W, H, sx: shot.offsetLeft, sy: shot.offsetTop, colW: col?.clientWidth ?? 270 };
      setGeo((old) => (old && JSON.stringify(old) === JSON.stringify(g) ? old : g));
    };
    measure();
    const ro = new ResizeObserver(measure);
    if (stageRef.current) ro.observe(stageRef.current);
    if (shotRef.current) ro.observe(shotRef.current);
    return () => ro.disconnect();
  }, [src]);

  const wide = (geo?.stageW ?? 0) >= WIDE_STAGE;
  const sideOf = (p: Pin): Side => sideFor({ x: p.box[0], y: p.box[1], w: p.box[2], h: p.box[3] }, wide);
  const columnPins = pins.filter((p) => !free.has(p.dom_id)).sort((a, b) => a.box[1] - b.box[1]);

  // Place the columns once the cards have heights. Deliberately runs after every render (a card's
  // height changes with tags, edits and width) and sets state only when the placement changes.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    if (!geo || !geo.H) return;
    const next: Record<string, { top: number; slide: number; z: number }> = {};
    const nextStacked: Record<Side, boolean> = { L: false, R: false };
    let bottom = geo.H;
    for (const side of ["L", "R"] as Side[]) {
      const col = columnPins.filter((p) => sideOf(p) === side);
      const cards = col.map((p) => ({
        want: Math.max(0, (p.box[1] + p.box[3] / 2) * geo.H - 20),
        height: cardEls.current.get(p.dom_id)?.offsetHeight ?? 120,
      }));
      const { placed, stacked: st, bottom: b } = placeColumn(cards, geo.H, props.stack === "diagonal");
      col.forEach((p, i) => (next[p.dom_id] = { top: placed[i].top, slide: placed[i].slide, z: 2 + i }));
      nextStacked[side] = st;
      bottom = Math.max(bottom, b);
    }
    for (const d of free) {
      const s = spots[d];
      const h = cardEls.current.get(d)?.offsetHeight ?? 120;
      bottom = Math.max(bottom, geo.sy + s.y * geo.H + h);
    }
    setTops((old) => (JSON.stringify(old) === JSON.stringify(next) ? old : next));
    setStacked((old) => (old.L === nextStacked.L && old.R === nextStacked.R ? old : nextStacked));
    setColH((old) => (old === bottom ? old : bottom));
  });

  // Leaders, once everything has settled; after every render for the same reason, set on change.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  useLayoutEffect(() => {
    const board = boardRef.current;
    if (!geo || !geo.H || !board) return;
    const bb = board.getBoundingClientRect();
    const next: { id: string; d: string; end: [number, number] }[] = [];
    for (const p of pins) {
      const el = cardEls.current.get(p.dom_id);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      const card = { left: r.left - bb.left, top: r.top - bb.top, width: r.width, height: r.height };
      const elem = {
        left: geo.sx + p.box[0] * geo.W, top: geo.sy + p.box[1] * geo.H,
        width: p.box[2] * geo.W, height: p.box[3] * geo.H,
      };
      const { d, end } = leaderPath(card, elem);
      next.push({ id: p.dom_id, d, end });
    }
    setLeaders((old) => (JSON.stringify(old) === JSON.stringify(next) ? old : next));
  });

  // Bring forward.
  const lift = (dom: string | null) => setFocused(dom);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setFocused(null);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  // Drag to rearrange: the card's top edge and the margin under its timecode are the grips.
  const startDrag = (dom: string) => (e: React.PointerEvent) => {
    if (e.button !== 0 || !geo || !boardRef.current) return;
    e.preventDefault();
    e.stopPropagation();
    const el = cardEls.current.get(dom);
    if (!el) return;
    const bb = boardRef.current.getBoundingClientRect();
    const r = el.getBoundingClientRect();
    const z = topZ() + 1;
    const start = { x: e.clientX, y: e.clientY, left: r.left - bb.left, top: r.top - bb.top };
    setFocused(null);
    setDrag({ dom, left: start.left, top: start.top, width: r.width, z });
    const target = e.currentTarget as HTMLElement;
    target.setPointerCapture(e.pointerId);
    const move = (ev: PointerEvent) =>
      setDrag({ dom, left: start.left + ev.clientX - start.x, top: Math.max(0, start.top + ev.clientY - start.y), width: r.width, z });
    const up = (ev: PointerEvent) => {
      target.removeEventListener("pointermove", move);
      target.removeEventListener("pointerup", up);
      target.removeEventListener("pointercancel", up);
      const left = start.left + ev.clientX - start.x;
      const top = Math.max(0, start.top + ev.clientY - start.y);
      putSpot(still, dom, { x: (left - geo.sx) / geo.W, y: (top - geo.sy) / geo.H, z });
      setSpots(spotsFor(still));
      setDrag(null);
    };
    target.addEventListener("pointermove", move);
    target.addEventListener("pointerup", up);
    target.addEventListener("pointercancel", up);
  };

  const cardFor = (dom: string, style: React.CSSProperties, pin?: Pin) => {
    const q = byId.get(dom);
    if (!q) return null;
    return (
      <ScreenCard
        key={dom}
        quote={q}
        phrase={pin?.phrase ?? ""}
        text={store.edits[dom] ?? q.text}
        starred={!!store.starred[dom]}
        tags={store.tags[dom] ?? []}
        focused={focused === dom}
        dragging={drag?.dom === dom}
        vocabulary={props.vocabulary}
        groupedVocabulary={props.groupedVocabulary}
        tagInfo={props.tagInfo}
        style={style}
        pin={pin ? dom : undefined}
        register={(el) => {
          if (el) cardEls.current.set(dom, el);
          else cardEls.current.delete(dom);
        }}
        onEnter={() => props.front === "hover" && !drag && lift(dom)}
        onLeave={() => props.front === "hover" && !drag && lift(null)}
        onClick={(e) => {
          if (props.front !== "click") return;
          if ((e.target as HTMLElement).closest("button, input, [role=button], .screens-grip, .tag-input-wrap")) return;
          e.stopPropagation();
          lift(focused === dom ? null : dom);
        }}
        onGrip={startDrag(dom)}
      />
    );
  };

  const placed = (dom: string): React.CSSProperties => {
    const p = tops[dom];
    return p
      ? ({ top: p.top, "--slide": `${p.slide}px`, "--stack": p.z } as React.CSSProperties)
      : { top: 0, visibility: "hidden" };
  };
  const freeStyle = (dom: string): React.CSSProperties => {
    if (drag?.dom === dom) return { left: drag.left, top: drag.top, width: drag.width, zIndex: drag.z };
    const s = spots[dom];
    if (!geo || !s) return { visibility: "hidden" };
    return { left: geo.sx + s.x * geo.W, top: geo.sy + s.y * geo.H, width: geo.colW, zIndex: s.z };
  };
  const dragOutOfColumn = drag && !free.has(drag.dom) ? drag.dom : null;

  const counterItems: CounterItem[] = hiddenHere.map((d) => {
    const q = byId.get(d)!;
    return {
      domId: d, timecode: formatTimecode(q.start_timecode), seconds: q.start_timecode,
      participantId: q.participant_id, previewText: store.edits[d] ?? q.text, hasMedia: false,
    };
  });

  const said = pins.length + rest.length;
  const people = screen.tabs.length;
  return (
    <>
      <div className="section-heading">
        <h1>{screenTitle(screen, tab)}</h1>
        <div className="section-heading-action screens-who">
          {screen.tabs.length > 1 ? (
            screen.tabs.map((t, j) => (
              <button key={`${t.session_id}@${t.t}`} aria-pressed={j === tabIdx} title={t.heading} onClick={() => props.onTab(j)}>
                <PersonBadge code={t.code} role="participant" />
              </button>
            ))
          ) : (
            <PersonBadge code={tab.code} role="participant" />
          )}
        </div>
      </div>
      <p className="screens-sub">
        {screen.name.startsWith("/") && <code>{screen.name}</code>}
        <span>
          {tab.code}’s screen at <span className="timecode">{formatTimecode(tab.t)}</span>
        </span>
        <span>
          {said} {said === 1 ? "quote" : "quotes"}
          {people > 1 ? ` from ${people} participants` : ""}
        </span>
        <span className="screens-hidden-slot">
          <Counter
            count={hiddenHere.length}
            items={counterItems}
            isOpen={hiddenOpen}
            onToggle={() => setHiddenOpen((o) => !o)}
            onUnhide={(d) => unhideQuotes([d])}
            onUnhideAll={() => {
              unhideQuotes(hiddenHere);
              setHiddenOpen(false);
            }}
          />
        </span>
        {Object.keys(spots).length > 0 && (
          <button
            className="screens-putback"
            onClick={() => {
              clearSpots(still);
              setSpots({});
            }}
          >
            Put the quotes back
          </button>
        )}
      </p>
      {/* A click on empty board puts a click-mode card back: pointer only, Escape does it from the keyboard. */}
      {/* eslint-disable-next-line jsx-a11y/click-events-have-key-events, jsx-a11y/no-static-element-interactions */}
      <div
        className={`screens-stage${focused ? " focus" : ""}${drag ? " dragging" : ""}`}
        ref={stageRef}
        onClick={() => props.front === "click" && lift(null)}
      >
        <div className="screens-board" ref={boardRef} style={{ minHeight: colH || undefined }}>
          <div className={`screens-col screens-col-l${stacked.L ? " stacked" : ""}${props.stack === "diagonal" ? " diagonal" : ""}`} style={{ height: colH || undefined }}>
            {columnPins.filter((p) => sideOf(p) === "L" && p.dom_id !== dragOutOfColumn).map((p) => cardFor(p.dom_id, placed(p.dom_id), p))}
          </div>
          <div className="screens-shot" ref={shotRef}>
            {src ? (
              <img alt="" src={src} />
            ) : (
              <div className="screens-shot-wait">
                {stillError && <span className="screens-shot-error">Screengrab unavailable: {stillError}</span>}
              </div>
            )}
            {geo &&
              pins.map((p) => (
                <div
                  key={p.dom_id}
                  className={`screens-hl${focused === p.dom_id ? " on" : ""}`}
                  style={{
                    left: p.box[0] * geo.W - 3, top: p.box[1] * geo.H - 3,
                    width: p.box[2] * geo.W + 6, height: p.box[3] * geo.H + 6,
                  }}
                />
              ))}
          </div>
          <div className={`screens-col screens-col-r${stacked.R ? " stacked" : ""}${props.stack === "diagonal" ? " diagonal" : ""}`} style={{ height: colH || undefined }}>
            {columnPins.filter((p) => sideOf(p) === "R" && p.dom_id !== dragOutOfColumn).map((p) => cardFor(p.dom_id, placed(p.dom_id), p))}
          </div>
          <svg className="screens-leaders" aria-hidden="true">
            {leaders.map((l) => (
              <g key={l.id} className={focused === l.id ? "on" : undefined}>
                <path d={l.d} />
                <circle cx={l.end[0]} cy={l.end[1]} r={2.5} />
              </g>
            ))}
          </svg>
          <div className="screens-free">
            {[...free, ...(dragOutOfColumn ? [dragOutOfColumn] : [])]
              .filter((d, i, a) => a.indexOf(d) === i)
              .map((d) => cardFor(d, freeStyle(d), pinByDom.get(d)))}
          </div>
        </div>
        <div className="screens-loose">
          {rest.filter((d) => !free.has(d) && d !== dragOutOfColumn).map((d) => cardFor(d, {}))}
        </div>
      </div>
    </>
  );
}
