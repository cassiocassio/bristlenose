/**
 * PlaybackScrollKeeper — keeps the reading position while a running AutoCode lands tags.
 *
 * Renders nothing. After every change the playback store publishes has been drawn, it scrolls
 * the page back by however far the quote card at the top of the window moved (WebKit only: the
 * other engines anchor the scroll themselves). See `restoreScrollAnchor` in
 * `contexts/AutoCodePlaybackView.ts`; mounted once, by AppLayout.
 *
 * @module PlaybackScrollKeeper
 */

import { useLayoutEffect } from "react";
import { restoreScrollAnchor, usePlayback } from "../contexts/AutoCodePlaybackView";

export function PlaybackScrollKeeper(): null {
  const snap = usePlayback();
  useLayoutEffect(() => {
    restoreScrollAnchor();
  }, [snap]);
  return null;
}
