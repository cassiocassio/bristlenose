import { Component, type ReactNode } from "react";
import { useInRouterContext, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

/**
 * Error boundary for one part of the report around the lens (R85). A part that
 * throws while rendering shows a short message where it was, instead of
 * reaching the `/report` route boundary and blanking the whole report. The
 * lens and the other parts keep working.
 *
 * Two uses. `SidebarLayout` wraps the side panels: the left panel and the tag
 * sidebar say "This sidebar couldn’t be shown", and the minimap is `quiet`.
 * `AppLayout` and the modals wrap the chrome, with `part`, which says "This
 * couldn’t be shown" (`labels.partError`): the header and nav in their bar's
 * slot (one row, `.center > .bn-panel-error` in toolbar.css), the footer, the
 * activity chips and the invisible syncs `quiet`, and each modal's content inside its own
 * `.bn-modal`, so the overlay, the × and Escape, which the modal owns, still
 * close it.
 *
 * A boundary catches only what renders below it, and a modal's content is
 * inline JSX evaluated in the modal's own render, above anything it wraps. So
 * the content may be passed as a function: it is then called inside the
 * boundary (by `Deferred`), and a throw in it is caught here. A throw in the
 * modal's own body (its hooks, or a value it computes before returning) is
 * still above the boundary and blanks the report; keep that body small.
 *
 * Retry remounts the part, which refetches whatever it reads; choosing
 * another lens (any route change) clears the error too, the same way React
 * Router clears the per-lens boundary. `reload` makes Retry reload the page
 * instead, as RouteError's does: the header and nav take it, because most
 * render crashes are deterministic and a remount with the same data crashes
 * again, while a reload refetches the data and the code chunks (edits save as
 * they are made, so it loses nothing). `quiet` renders nothing instead of a
 * message, where a message would be noise or there is no room for one.
 *
 * As with RouteError, the error is logged to the console, never shown. The
 * fallback carries `bn-route-error` too, so it takes the same button spacing
 * and the e2e crash check (`.bn-route-error`) still sees a panel crash.
 */
export function PanelErrorBoundary({
  children,
  quiet = false,
  part = false,
  reload = false,
}: {
  children: ReactNode | (() => ReactNode);
  quiet?: boolean;
  part?: boolean;
  reload?: boolean;
}) {
  // SidebarLayout is also mounted without a router (its own unit tests), so the
  // route-change reset is read only when there is one.
  return useInRouterContext() ? (
    <ResetOnRouteChange quiet={quiet} part={part} reload={reload}>{children}</ResetOnRouteChange>
  ) : (
    <Boundary quiet={quiet} part={part} reload={reload}>{children}</Boundary>
  );
}

function ResetOnRouteChange({ children, quiet, part, reload }: Omit<BoundaryProps, "resetKey">) {
  const { pathname } = useLocation();
  return (
    <Boundary quiet={quiet} part={part} reload={reload} resetKey={pathname}>
      {children}
    </Boundary>
  );
}

/** Renders a function child in its own render, so a throw in it is below the boundary. */
function Deferred({ render }: { render: () => ReactNode }) {
  return render();
}

interface BoundaryProps {
  children: ReactNode | (() => ReactNode);
  quiet: boolean;
  part: boolean;
  reload: boolean;
  resetKey?: string;
}

interface BoundaryState {
  failed: boolean;
  resetKey?: string;
}

class Boundary extends Component<BoundaryProps, BoundaryState> {
  state: BoundaryState = { failed: false, resetKey: this.props.resetKey };

  static getDerivedStateFromError(): Partial<BoundaryState> {
    return { failed: true };
  }

  static getDerivedStateFromProps(props: BoundaryProps, state: BoundaryState): Partial<BoundaryState> | null {
    return props.resetKey !== state.resetKey ? { failed: false, resetKey: props.resetKey } : null;
  }

  componentDidCatch(error: unknown) {
    console.error("[PanelError]", error);
  }

  render() {
    const { children } = this.props;
    if (!this.state.failed) return typeof children === "function" ? <Deferred render={children} /> : children;
    if (this.props.quiet) return null;
    const onRetry = this.props.reload
      ? () => window.location.reload()
      : () => this.setState({ failed: false });
    return <PanelFallback part={this.props.part} onRetry={onRetry} />;
  }
}

function PanelFallback({ part, onRetry }: { part: boolean; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="bn-empty-state bn-route-error bn-panel-error" role="alert">
      <p>{t(part ? "labels.partError" : "labels.panelError")}</p>
      <button type="button" className="bn-btn bn-btn-primary" onClick={onRetry}>
        {t("buttons.retry")}
      </button>
    </div>
  );
}
