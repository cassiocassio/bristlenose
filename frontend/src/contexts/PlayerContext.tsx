/**
 * PlayerContext — popout video/audio player integration.
 *
 * Replaces `player.js` in serve mode.  Manages the popout player window
 * lifecycle, `postMessage` IPC for playback state, and glow highlighting
 * on timecodes.
 *
 * Architecture: glow state is managed via direct DOM class manipulation
 * (refs, not React state) because timeupdate messages arrive ~4x/sec.
 * Storing currentTime in state would re-render hundreds of quote cards
 * per second.  Instead, the provider's effect adds/removes CSS classes
 * (`bn-timecode-glow`, `bn-timecode-playing`) directly on DOM elements.
 *
 * @module PlayerContext
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  type ReactNode,
} from "react";
import { useLocation } from "react-router-dom";

// ── Types ────────────────────────────────────────────────────────────────

interface VideoMap {
  [key: string]: string; // participant/session ID → media URI
}

interface GlowEntry {
  el: Element;
  start: number;
  end: number;
}

interface PlayerContextValue {
  seekTo: (pid: string, seconds: number) => void;
}

// ── Context ──────────────────────────────────────────────────────────────

export const PlayerContext = createContext<PlayerContextValue | null>(null);

// ── Hook ─────────────────────────────────────────────────────────────────

export function usePlayer(): PlayerContextValue {
  const ctx = useContext(PlayerContext);
  if (!ctx) throw new Error("usePlayer must be used within PlayerProvider");
  return ctx;
}

// ── Provider ─────────────────────────────────────────────────────────────

export function PlayerProvider({ children }: { children: ReactNode }) {
  // Server-injected globals (read once on mount)
  const videoMapRef = useRef<VideoMap>({});
  const playerUrlRef = useRef("assets/bristlenose-player.html");

  // Popout window handle
  const playerWinRef = useRef<Window | null>(null);

  // Glow state — refs, not React state (performance)
  const glowIndexRef = useRef<Record<string, GlowEntry[]> | null>(null);
  const glowActiveRef = useRef<Set<Element>>(new Set());

  // Fetch video map from API (or fall back to window globals for legacy mode)
  useEffect(() => {
    const win = window as unknown as Record<string, unknown>;
    // Legacy fallback: use window globals if present (static render path)
    if (win.BRISTLENOSE_VIDEO_MAP) {
      videoMapRef.current = win.BRISTLENOSE_VIDEO_MAP as VideoMap;
      if (typeof win.BRISTLENOSE_PLAYER_URL === "string") {
        playerUrlRef.current = win.BRISTLENOSE_PLAYER_URL;
      }
      return;
    }
    // SPA mode: fetch from API
    fetch("/api/projects/1/video-map")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data) {
          videoMapRef.current = data.video_map ?? {};
          if (data.player_url) playerUrlRef.current = data.player_url;
        }
      })
      .catch(() => {});
  }, []);

  // ── Glow helpers ─────────────────────────────────────────────────────

  const buildGlowIndex = useCallback(() => {
    const index: Record<string, GlowEntry[]> = {};

    // Transcript page segments — key by session ID (from URL), not speaker
    // code, because the popout player sends pid=sessionId in timeupdate
    // messages (e.g. "s1"), while data-participant holds the speaker code
    // (e.g. "m1", "p1").
    const segments = document.querySelectorAll<HTMLElement>(
      ".transcript-segment[data-start-seconds][data-end-seconds]",
    );
    // Extract session ID from pathname: /report/sessions/:sessionId
    const sessionMatch = window.location.pathname.match(
      /\/report\/sessions\/([^/]+)/,
    );
    const sessionId = sessionMatch?.[1] ?? null;
    segments.forEach((seg) => {
      // Use session ID when on a transcript page; fall back to
      // data-participant for other pages (shouldn't happen, but safe).
      const pid = sessionId ?? seg.getAttribute("data-participant");
      if (!pid) return;
      const start = parseFloat(seg.getAttribute("data-start-seconds") ?? "");
      const end = parseFloat(seg.getAttribute("data-end-seconds") ?? "");
      if (isNaN(start) || isNaN(end)) return;
      if (!index[pid]) index[pid] = [];
      index[pid].push({ el: seg, start, end });
    });

    // Fix zero-length segments (end == start) — use next segment's start
    for (const pid of Object.keys(index)) {
      const entries = index[pid];
      for (let i = 0; i < entries.length; i++) {
        if (entries[i].end <= entries[i].start) {
          entries[i].end =
            i + 1 < entries.length ? entries[i + 1].start : Infinity;
        }
      }
    }

    // Report page blockquotes
    const quotes = document.querySelectorAll<HTMLElement>(
      "blockquote[data-participant]",
    );
    quotes.forEach((bq) => {
      const pid = bq.getAttribute("data-participant");
      if (!pid) return;
      const tc = bq.querySelector<HTMLElement>(
        "a.timecode[data-seconds][data-end-seconds]",
      );
      if (!tc) return;
      const start = parseFloat(tc.getAttribute("data-seconds") ?? "");
      const end = parseFloat(tc.getAttribute("data-end-seconds") ?? "");
      if (isNaN(start) || isNaN(end)) return;
      if (!index[pid]) index[pid] = [];
      index[pid].push({ el: bq, start, end });
    });

    glowIndexRef.current = index;
  }, []);

  const clearAllGlow = useCallback(() => {
    glowActiveRef.current.forEach((el) => {
      el.classList.remove("bn-timecode-glow", "bn-timecode-playing");
      (el as HTMLElement).style.removeProperty("--bn-segment-progress");
    });
    glowActiveRef.current = new Set();
  }, []);

  const updateGlow = useCallback(
    (pid: string, seconds: number, playing: boolean) => {
      if (!glowIndexRef.current) buildGlowIndex();

      const entries = glowIndexRef.current?.[pid] ?? [];
      const newActive = new Set<Element>();

      // Map element → corrected glow entry for progress computation
      const activeEntries = new Map<Element, GlowEntry>();

      for (const entry of entries) {
        if (seconds >= entry.start && seconds < entry.end) {
          newActive.add(entry.el);
          activeEntries.set(entry.el, entry);
        }
      }

      // Remove glow from elements no longer active
      glowActiveRef.current.forEach((el) => {
        if (!newActive.has(el)) {
          el.classList.remove("bn-timecode-glow", "bn-timecode-playing");
          (el as HTMLElement).style.removeProperty("--bn-segment-progress");
        }
      });

      // Add glow to newly active elements; auto-scroll transcript segments
      newActive.forEach((el) => {
        if (
          !glowActiveRef.current.has(el) &&
          el.classList.contains("transcript-segment")
        ) {
          el.scrollIntoView({ behavior: "smooth", block: "center" });
        }
        el.classList.add("bn-timecode-glow");
        if (playing) {
          el.classList.add("bn-timecode-playing");
        } else {
          el.classList.remove("bn-timecode-playing");
        }

        // Progress fill: set --bn-segment-progress (0–1) for transcript
        // segments so the CSS ::before left-border grows top-to-bottom.
        // Uses corrected start/end from the glow index (handles zero-length
        // segments whose end was fixed to the next segment's start).
        const entry = activeEntries.get(el);
        if (entry && el.classList.contains("transcript-segment")) {
          const dur = entry.end - entry.start;
          const progress =
            dur > 0 && isFinite(dur)
              ? Math.min(1, Math.max(0, (seconds - entry.start) / dur))
              : 0;
          (el as HTMLElement).style.setProperty(
            "--bn-segment-progress",
            String(progress),
          );
        }
      });

      glowActiveRef.current = newActive;
    },
    [buildGlowIndex],
  );

  const updatePlayState = useCallback((playing: boolean) => {
    glowActiveRef.current.forEach((el) => {
      if (playing) {
        el.classList.add("bn-timecode-playing");
      } else {
        el.classList.remove("bn-timecode-playing");
      }
    });
  }, []);

  // ── seekTo ───────────────────────────────────────────────────────────

  const seekTo = useCallback((pid: string, seconds: number) => {
    const uri = videoMapRef.current[pid];
    if (!uri) return;

    const msg = { type: "bristlenose-seek", pid, src: uri, t: seconds };
    const hash =
      "#src=" +
      encodeURIComponent(uri) +
      "&t=" +
      seconds +
      "&pid=" +
      encodeURIComponent(pid);

    if (!playerWinRef.current || playerWinRef.current.closed) {
      const win = window.open(
        playerUrlRef.current + hash,
        "bristlenose-player",
        "width=720,height=480,resizable=yes,scrollbars=no",
      );
      playerWinRef.current = win;
    } else {
      playerWinRef.current.postMessage(msg, "*");
      playerWinRef.current.focus();
    }
  }, []);

  // ── Main effect: message listener + close polling ────────────────────

  useEffect(() => {
    const handleMessage = (e: MessageEvent) => {
      const d = e.data;
      if (!d || typeof d.type !== "string") return;

      if (d.type === "bristlenose-timeupdate" && d.pid) {
        const playing = d.playing !== undefined ? d.playing : true;
        updateGlow(d.pid, d.seconds, playing);
      } else if (d.type === "bristlenose-playstate" && d.pid) {
        updatePlayState(d.playing);
      }
    };

    window.addEventListener("message", handleMessage);

    // Poll for player window closure
    const pollInterval = setInterval(() => {
      if (playerWinRef.current && playerWinRef.current.closed) {
        playerWinRef.current = null;
        clearAllGlow();
      }
    }, 1000);

    return () => {
      window.removeEventListener("message", handleMessage);
      clearInterval(pollInterval);
      clearAllGlow();
    };
  }, [updateGlow, updatePlayState, clearAllGlow]);

  // ── Backward-compat shim ─────────────────────────────────────────────

  useEffect(() => {
    (window as unknown as Record<string, unknown>).seekTo = seekTo;
  }, [seekTo]);

  // ── Clear glow index on route change (force rebuild for new DOM) ─────

  const location = useLocation();
  useEffect(() => {
    glowIndexRef.current = null;
  }, [location.pathname]);

  // ── Render ───────────────────────────────────────────────────────────

  const value: PlayerContextValue = { seekTo };

  return (
    <PlayerContext.Provider value={value}>{children}</PlayerContext.Provider>
  );
}
