/**
 * A screen's thumbnail in the transcript's margin (docs/design-transcript-gutter.md): it hangs
 * under the screen's title, out of flow, fading out under whatever follows, and surfaces whole
 * while its entry is hovered (transcript-gutter.css).
 *
 * The still is a participant's screen, served behind the bearer token (GET /screens/still) and
 * never part of an export; it is fetched only when the thumbnail nears the viewport, once.
 */
import { useEffect, useRef, useState, type MouseEvent } from "react";
import { apiGet } from "../../utils/api";
import { stillUrl, type ScreenTabLike } from "../screens/screenModel";

/** Twice the widest the margin draws it, for a sharp still on a Retina display. */
const STILL_W = 280;
const cache = new Map<string, string | null>();
const waiting = new Map<string, Promise<string | null>>();

function fetchStill(url: string): Promise<string | null> {
  let p = waiting.get(url);
  if (!p) {
    p = apiGet<{ src: string }>(url)
      .then((r) => r.src)
      .catch(() => null)
      .then((src) => {
        cache.set(url, src);
        waiting.delete(url);
        return src;
      });
    waiting.set(url, p);
  }
  return p;
}

interface GutterThumbProps {
  tab: ScreenTabLike;
  href: string;
  onFollow: (e: MouseEvent) => void;
}

export function GutterThumb({ tab, href, onFollow }: GutterThumbProps) {
  const url = stillUrl(tab, STILL_W);
  const ref = useRef<HTMLAnchorElement | null>(null);
  const [src, setSrc] = useState<string | null>(() => cache.get(url) ?? null);

  useEffect(() => {
    if (cache.has(url)) return;
    let live = true;
    const load = () => {
      void fetchStill(url).then((s) => {
        if (live) setSrc(s);
      });
    };
    const el = ref.current;
    if (!el || typeof IntersectionObserver === "undefined") {
      load();
      return () => {
        live = false;
      };
    }
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          load();
        }
      },
      { rootMargin: "600px 0px" },
    );
    io.observe(el);
    return () => {
      live = false;
      io.disconnect();
    };
  }, [url]);

  // The same link as the screen's title beside it, so it is not a second stop for the keyboard
  // or a second name for a screen reader.
  return (
    <a ref={ref} className="bn-gutter-thumb" href={href} onClick={onFollow} tabIndex={-1} aria-hidden="true">
      {src ? <img src={src} alt="" /> : <span className="bn-gutter-thumb-empty" />}
    </a>
  );
}
