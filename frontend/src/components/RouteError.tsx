import { useRouteError, isRouteErrorResponse } from "react-router-dom";
import { useTranslation } from "react-i18next";

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
 * again or choose another lens. Without it, it replaces the whole layout.
 */
export function RouteError({ scope = "report" }: { scope?: "report" | "lens" }) {
  const error = useRouteError();

  if (error) {
    const detail = isRouteErrorResponse(error)
      ? `${error.status} ${error.statusText}`
      : error;
    console.error("[RouteError]", detail);
  }

  return <ErrorNotice scope={scope} />;
}

/**
 * The fallback itself: a calm sentence and Retry. RouteError renders it for a
 * crash; a lens renders it with `scope="lens"` when its own read fails (R86),
 * which used to print the wire string ("GET /transcripts/s3 404: …") in
 * English, with nothing to do about it. The caller logs the error; this shows
 * none of it.
 */
export function ErrorNotice({ scope = "report" }: { scope?: "report" | "lens" }) {
  const { t } = useTranslation();
  return (
    <div className="bn-empty-state bn-route-error" role="alert">
      <p>{scope === "lens" ? t("labels.lensError") : t("labels.error")}</p>
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
