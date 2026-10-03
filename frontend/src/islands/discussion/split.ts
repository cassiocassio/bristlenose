/**
 * The split between navigator and session column takes the shipped
 * left-panel floor and keyboard step (useDragResize) — and ONE departure: its
 * ceiling is 60% of the lens, not the shared 480px, so a study with many
 * sessions can widen the navigator until its rows of session badges fit.
 */
export { MIN_WIDTH } from "../../hooks/useDragResize";

/** ±10px per arrow key, matching useDragResize's RESIZE_STEP (not exported there). */
export const RESIZE_STEP = 10;
