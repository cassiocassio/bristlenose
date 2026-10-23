import { useCallback, useEffect, useRef, useState } from "react";

/**
 * How a lens reads its data, and reads it again after a run (owner, 23 Oct 2026: #33 refined,
 * post-run dimming).
 *
 * - **first**: on mount, and whenever `key` changes (a project switch, a write that renumbers).
 *   A lens re-reads once when it is opened because it remounts; there is no re-read on focus.
 * - **reload**: the lens asks (`reload()`), e.g. after tags changed elsewhere.
 * - **refresh**: `refreshKey` moved (a run imported or finished). Nothing shows while it is in
 *   flight. If it fails it is tried once more after `RETRY_PAUSE_MS`, silently, and never again:
 *   the console says why, the drawn lens stays as it was, and ⌘R is the remedy. When new data
 *   arrives over a lens already drawn, `handingOver` is true for `HANDOVER_MS`, which plays the
 *   dim as the hand-over from old to new (`.bn-handover`, `organisms/toolbar.css`).
 *
 * Every failure goes to the console under `label`. `onError` hears only a failed first read or
 * reload, so the lens can say so when it has nothing drawn; over a drawn lens it should keep what
 * it has (R86). An answer older than one already applied is dropped, and so is any answer from
 * before the last `key` change.
 */
export const HANDOVER_MS = 240;
export const RETRY_PAUSE_MS = 2000;

export type LensReadKind = "first" | "reload" | "refresh";

export interface LensReadOptions<T> {
  read: () => Promise<T>;
  apply: (value: T, kind: LensReadKind) => void;
  onError?: (err: unknown, kind: "first" | "reload") => void;
  refreshKey: number;
  /** A change re-reads as a first read and sets aside every answer from before it. */
  key: string;
  /** Leads the console line for every failed read. */
  label: string;
}

export function useLensRead<T>({
  read,
  apply,
  onError,
  refreshKey,
  key,
  label,
}: LensReadOptions<T>): { reload: () => void; handingOver: boolean } {
  // Held in a ref, so callers need not memoise them and a new closure does not re-read.
  const fns = useRef({ read, apply, onError, label });
  useEffect(() => {
    fns.current = { read, apply, onError, label };
  });
  const tickets = useRef({ latest: 0, applied: 0, floor: 0 });
  const live = useRef(true);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const handoverTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const [handingOver, setHandingOver] = useState(false);

  useEffect(() => {
    live.current = true;
    return () => {
      live.current = false;
      clearTimeout(retryTimer.current);
      clearTimeout(handoverTimer.current);
    };
  }, []);

  const run = useCallback((kind: LensReadKind) => {
    const t = tickets.current;
    const go = (attempt: number) => {
      const ticket = ++t.latest;
      if (kind === "first") t.floor = ticket;
      const stale = () => ticket < t.floor || ticket <= t.applied;
      let reading: Promise<T>;
      try {
        reading = fns.current.read();
      } catch (e) {
        reading = Promise.reject(e); // a read that throws before its promise fails like one
      }
      reading.then(
        (value) => {
          if (!live.current || stale()) return;
          const drawn = t.applied > 0;
          // In the same callback, so React commits the new data and the class together.
          try {
            fns.current.apply(value, kind);
          } catch (e) {
            // A body the lens cannot take is a failed read, not a lens left loading.
            console.error(fns.current.label, e);
            if (kind !== "refresh") fns.current.onError?.(e, kind);
            return;
          }
          t.applied = ticket;
          // A second arrival while the dim is still playing extends it rather than replaying it.
          if (kind === "refresh" && drawn) {
            setHandingOver(true);
            clearTimeout(handoverTimer.current);
            handoverTimer.current = setTimeout(() => {
              if (live.current) setHandingOver(false);
            }, HANDOVER_MS);
          }
        },
        (err: unknown) => {
          if (!live.current) return;
          console.error(fns.current.label, err);
          if (stale()) return;
          if (kind !== "refresh") {
            fns.current.onError?.(err, kind);
            return;
          }
          if (attempt > 0) return; // tried twice: stop
          retryTimer.current = setTimeout(() => {
            // A newer read since covers it.
            if (live.current && t.latest === ticket) go(1);
          }, RETRY_PAUSE_MS);
        },
      );
    };
    go(0);
  }, []);

  useEffect(() => {
    run("first");
  }, [key, run]);

  const seenRefresh = useRef(refreshKey);
  useEffect(() => {
    if (seenRefresh.current === refreshKey) return;
    seenRefresh.current = refreshKey;
    run("refresh");
  }, [refreshKey, run]);

  const reload = useCallback(() => run("reload"), [run]);
  return { reload, handingOver };
}

/** The lens root's class while new data is being handed over. */
export function handoverClass(handingOver: boolean, baseClassName = ""): string {
  if (!handingOver) return baseClassName;
  return baseClassName ? `${baseClassName} bn-handover` : "bn-handover";
}
