import { useEffect, useState } from "react";
import { useRouteError, isRouteErrorResponse, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import i18n from "../i18n";
import {
  postOpenProblemReport,
  postReportError,
  REPORT_ERROR_FRAME_LIMIT,
} from "../shims/bridge";
import { isEmbedded } from "../utils/embedded";
import { getExportData } from "../utils/exportData";
import type { HealthResponse } from "../utils/health";
import { FeedbackModal } from "./FeedbackModal";
import { Icon } from "./Icon";

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
 * so the nav and sidebars stay. An unexpected lens crash names the affected
 * lens and offers the existing problem-report door when enabled; its working
 * navigation is already the way to leave it. Without it, it replaces the whole layout —
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

  if (scope === "report") return <ReportCrashNotice error={error} pathname={pathname} />;
  return <LensCrashNotice error={error} pathname={pathname} />;
}

/**
 * What a problem report from the crash pane starts with: the pane's sentence,
 * then the error and the page, the line the Mac popover's caption shows. No
 * project, path or stack frames: it is sent as the person's message.
 */
export function problemReportMessage(
  t: TFunction,
  error: unknown,
  pathname: string,
  headline = t("labels.reportError"),
): string {
  return `${headline}\n${describeError(error).message} · ${pathname}`;
}

/**
 * The whole report's crash pane offers feedback rather than a speculative
 * retry. A generic render crash has no user-controlled recovery, while its
 * bounded diagnostic is useful to Bristlenose. In the Mac app it opens this
 * window's native problem-report sheet; in a browser it opens the web form
 * once health confirms feedback is available.
 */
function ReportCrashNotice({ error, pathname }: { error: unknown; pathname: string }) {
  const { t } = useTranslation();
  const embedded = isEmbedded();
  const health = useCrashHealth(!embedded);
  const [formOpen, setFormOpen] = useState(false);
  const message = problemReportMessage(t, error, pathname);
  const label =
    embedded && i18n.exists("desktop:menu.help.sendFeedback")
      ? t("desktop:menu.help.sendFeedback")
      : t("footer.sendFeedback");
  return (
    <div className="bn-empty-state bn-route-error" role="alert">
      <p>{t("labels.reportError")}</p>
      {(embedded || health?.feedback.enabled === true) && (
        <button
          type="button"
          className="bn-btn bn-btn-secondary"
          onClick={() => (embedded ? postOpenProblemReport(message) : setFormOpen(true))}
        >
          {label}
        </button>
      )}
      {!embedded && health && (
        <FeedbackModal
          open={formOpen}
          onClose={() => setFormOpen(false)}
          health={health}
          mode={{ kind: "problem", initialMessage: message }}
        />
      )}
    </div>
  );
}

/** A route path's researcher-facing lens label, never a raw route segment. */
function lensName(pathname: string, t: TFunction): string {
  const segments = pathname.split("/").filter(Boolean);
  const segment = segments[segments.length - 1];
  const key = segment === "codebook" ? "codebook"
    : segment === "signals" ? "signals"
      : segment === "discussion" ? "discussion"
        : segment === "screens" ? "screens"
          : segment === "quotes" ? "quotes"
            : segment === "sessions" ? "sessions"
              : "project";
  return t(`nav.${key}`);
}

/** An unexpected crash inside one lens: navigation survives, so Retry is not a recovery plan. */
function LensCrashNotice({ error, pathname }: { error: unknown; pathname: string }) {
  const { t } = useTranslation();
  const embedded = isEmbedded();
  const health = useCrashHealth(!embedded);
  const [formOpen, setFormOpen] = useState(false);
  const lens = lensName(pathname, t);
  const headline = t("labels.lensCrash", {
    lens,
    defaultValue: `${lens} couldn’t be shown.`,
  });
  const context = t("labels.lensCrashContext", {
    lens,
    defaultValue: `Bristlenose hit an unexpected problem opening ${lens}.`,
  });
  const message = problemReportMessage(t, error, pathname, headline);
  const label =
    embedded && i18n.exists("desktop:menu.help.sendFeedback")
      ? t("desktop:menu.help.sendFeedback")
      : t("footer.sendFeedback");

  return (
    <div className="bn-empty-state bn-route-error bn-lens-crash" role="alert">
      <Icon name="broken" decorative px={32} className="bn-route-error-icon" />
      <p>{headline}</p>
      <p>{context}</p>
      {(embedded || health?.feedback.enabled === true) && (
        <button
          type="button"
          className="bn-btn bn-btn-secondary"
          onClick={() => (embedded ? postOpenProblemReport(message) : setFormOpen(true))}
        >
          {label}
        </button>
      )}
      {!embedded && health && (
        <FeedbackModal
          open={formOpen}
          onClose={() => setFormOpen(false)}
          health={health}
          mode={{ kind: "problem", initialMessage: message }}
        />
      )}
    </div>
  );
}

/**
 * The health answer the crashed layout would have read (whether feedback is
 * on, its URL, the version), for the browser's form. The export carries its
 * own; a served report asks once. Null until known.
 */
function useCrashHealth(wanted: boolean): HealthResponse | null {
  const [health, setHealth] = useState<HealthResponse | null>(
    () => getExportData()?.health ?? null,
  );
  useEffect(() => {
    if (!wanted || getExportData()) return;
    let live = true;
    fetch("/api/health")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (live && data?.version) setHealth(data as HealthResponse);
      })
      .catch(() => {});
    return () => {
      live = false;
    };
  }, [wanted]);
  return health;
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
 * The fallback itself: a calm sentence and Retry for a classified read failure,
 * not an unexpected route crash. Lenses render it when their own read fails (R86),
 * which used to print the wire string ("GET /transcripts/s3 404: …") in
 * English, with nothing to do about it. The caller logs the error; this shows
 * none of it.
 *
 * The report sentence is `labels.reportError` ("This report couldn't be
 * shown."). Unexpected route crashes use `ReportCrashNotice` or
 * `LensCrashNotice`; feedback is the only honest recovery for those states.
 */
export function ErrorNotice({
  scope = "report",
  onRetry = () => window.location.reload(),
}: {
  scope?: "report" | "lens";
  /** The report's crash pane marks its Retry (`retryReport`); a lens's does not. */
  onRetry?: () => void;
}) {
  const { t } = useTranslation();
  return (
    <div className="bn-empty-state bn-route-error" role="alert">
      <p>{scope === "lens" ? t("labels.lensError") : t("labels.reportError")}</p>
      <button
        type="button"
        className="bn-btn bn-btn-primary"
        onClick={onRetry}
      >
        {t("buttons.retry")}
      </button>
    </div>
  );
}
