import { useCallback, useState } from "react";

export interface RefetchingState {
  isRefetching: boolean;
  beginRefetch: () => void;
  endRefetch: () => void;
}

export function useRefetching(): RefetchingState {
  const [isRefetching, setIsRefetching] = useState(false);
  const beginRefetch = useCallback(() => setIsRefetching(true), []);
  const endRefetch = useCallback(() => setIsRefetching(false), []);
  return { isRefetching, beginRefetch, endRefetch };
}

/**
 * Props for the dimmed-section wrapper during refetch. Use via spread on
 * a `<section>` (or any block element). The `inert` attribute blocks AT
 * and keyboard input — opacity alone would only dim visuals while
 * leaving the section interactive.
 *
 * @param baseClassName  Existing className on the element, if any.
 *                       Returned with `bn-refetching` appended when
 *                       `isRefetching` is true.
 */
export function refetchOverlayProps(
  isRefetching: boolean,
  baseClassName = "",
): { className: string; inert?: boolean } {
  if (!isRefetching) {
    return { className: baseClassName };
  }
  const className = baseClassName
    ? `${baseClassName} bn-refetching`
    : "bn-refetching";
  return { className, inert: true };
}
