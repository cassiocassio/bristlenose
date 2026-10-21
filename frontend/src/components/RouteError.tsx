import { useEffect } from "react";
import { useRouteError, isRouteErrorResponse, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { postReportError, REPORT_ERROR_FRAME_LIMIT } from "../shims/bridge";

/**
 * Route-level error fallback. React Router renders this via the route's
 * `errorElement` when a route element (or any descendant) throws during
 * render, or a loader/action rejects. It stops a raw React crash — a white
 * screen or dev-facing stack trace — from ever reaching a user; instead they
 * get a calm message and a reload affordance.
 *
 * The underlying error is logged to the console for diagnostics but never
 * surfaced in the UI (a raw "Cannot read properties of undefined" is exactly
 * the surprise this guard exists to prevent).
 *
 * `scope="lens"` is the per-lens boundary (R85): it renders inside the layout,
 * so the nav and sidebars stay, and its sentence says the researcher can try
 * again or choose another lens. Without it, it replaces the whole layout —
 * and, in the Mac app, tells the shell (`postReportError`, decision #2), which
 * lights the project's sidebar row and gives Copy details the stack. A lens
 * crash never does: the researcher can see it and leave it. A throw in a
 * modal's own body (its hooks, anything computed above its `return`) is above
 * the modal's boundary, so it is a whole-report crash and arrives here. The
 * shell clears the row on the next `route-change`, which the fresh layout
 * posts on mount after Retry's reload.
 */
export function RouteError({ scope = "report" }: { scope?: "report" | "lens" }) {
  const error = useRouteError();
  const { pathname } = useLocation();

  if (error) {
    const detail = isRouteErrorResponse(error)
      ? `${error.status} ${error.statusText}`
      : error;
    console.error("[RouteError]", detail);
  }

  // Once per crash, not per render: the effect re-runs when the error object
  // or the path changes — and a path change resets the boundary, so a second
  // throw is a new error object; the two deps name one event. The WKWebView
  // console is invisible in a release build, so this is the only road the
  // stack has to the researcher.
  useEffect(() => {
    if (scope !== "report" || !error) return;
    const { message, frames } = describeError(error);
    if (message === NO_MESSAGE) {
      // `throw ""`, a toString that throws: still a crash, and the shell drops
      // a payload with no message, so one is supplied and the oddity logged.
      console.error("[RouteError] crash with no message", error);
    }
    postReportError(pathname, message, frames);
  }, [scope, error, pathname]);

  return <ErrorNotice scope={scope} />;
}

/**
 * A thrown value as a sentence and its first stack frames. `TypeError: …` for
 * an `Error` (what the mockup shows), `404 Not Found` for a route response,
 * `String(x)` for anything else. Frames are the lines of `error.stack` that
 * are frames — V8 indents them with `at`, JavaScriptCore writes `fn@url` —
 * so the message line is never repeated as a frame.
 */
export function describeError(error: unknown): { message: string; frames: string[] } {
  // This runs in the error boundary's own render path: a throw here would be
  // a crash in the crash handler, with nothing left to catch it. So every read
  // of the thrown value is guarded, and the fallback is a sentence.
  try {
    if (isRouteErrorResponse(error)) {
      return { message: `${error.status} ${error.statusText}`, frames: [] };
    }
    if (error instanceof Error) {
      const stack = typeof error.stack === "string" ? error.stack : "";
      const frames = stack
        .split("\n")
        .map((line) => line.trim())
        .filter((line) => line.startsWith("at ") || /^[^\s]*@/.test(line))
        .slice(0, REPORT_ERROR_FRAME_LIMIT);
      return { message: `${error.name}: ${error.message}`, frames };
    }
    const text = String(error);
    return { message: text === "" ? NO_MESSAGE : text, frames: [] };
  } catch {
    return { message: NO_MESSAGE, frames: [] };
  }
}

/** What is posted for a thrown value that says nothing (`throw ""`, a toString that throws). */
export const NO_MESSAGE = "(no message)";

/**
 * The fallback itself: a calm sentence and Retry. RouteError renders it for a
 * crash; a lens renders it with `scope="lens"` when its own read fails (R86),
 * which used to print the wire string ("GET /transcripts/s3 404: …") in
 * English, with nothing to do about it. The caller logs the error; this shows
 * none of it.
 *
 * The report sentence is `labels.reportError` ("This report couldn't be
 * shown."), the lens sentence's sibling; it was the bare `labels.error`
 * ("Error") until 21 Oct 2026.
 */
export function ErrorNotice({ scope = "report" }: { scope?: "report" | "lens" }) {
  const { t } = useTranslation();
  return (
    <div className="bn-empty-state bn-route-error" role="alert">
      <p>{scope === "lens" ? t("labels.lensError") : t("labels.reportError")}</p>
      <button
        type="button"
        className="bn-btn bn-btn-primary"
        onClick={() => window.location.reload()}
      >
        {t("buttons.retry")}
      </button>
    </div>
  );
}
