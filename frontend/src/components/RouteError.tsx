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
 */
export function RouteError() {
  const error = useRouteError();
  const { t } = useTranslation();

  if (error) {
    const detail = isRouteErrorResponse(error)
      ? `${error.status} ${error.statusText}`
      : error;
    // eslint-disable-next-line no-console
    console.error("[RouteError]", detail);
  }

  return (
    <div className="bn-empty-state bn-route-error" role="alert">
      <p>{t("labels.error")}</p>
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
