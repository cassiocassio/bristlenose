import { Component, type ReactNode } from "react";
import { useInRouterContext, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";

/**
 * Error boundary for one side panel (R85). A sidebar or the minimap that
 * throws while rendering shows a short message in its own column, instead of
 * reaching the `/report` route boundary and blanking the whole report. The
 * lens, the nav and the other panels keep working.
 *
 * Retry remounts the panel, which refetches whatever it reads; choosing
 * another lens (any route change) clears the error too, the same way React
 * Router clears the per-lens boundary. `quiet` renders nothing instead of a
 * message, for a column too narrow to hold one (the minimap).
 *
 * As with RouteError, the error is logged to the console, never shown. The
 * fallback carries `bn-route-error` too, so it takes the same button spacing
 * and the e2e crash check (`.bn-route-error`) still sees a panel crash.
 */
export function PanelErrorBoundary({ children, quiet = false }: { children: ReactNode; quiet?: boolean }) {
  // SidebarLayout is also mounted without a router (its own unit tests), so the
  // route-change reset is read only when there is one.
  return useInRouterContext() ? (
    <ResetOnRouteChange quiet={quiet}>{children}</ResetOnRouteChange>
  ) : (
    <Boundary quiet={quiet}>{children}</Boundary>
  );
}

function ResetOnRouteChange({ children, quiet }: { children: ReactNode; quiet: boolean }) {
  const { pathname } = useLocation();
  return (
    <Boundary quiet={quiet} resetKey={pathname}>
      {children}
    </Boundary>
  );
}

interface BoundaryProps {
  children: ReactNode;
  quiet: boolean;
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
    if (!this.state.failed) return this.props.children;
    if (this.props.quiet) return null;
    return <PanelFallback onRetry={() => this.setState({ failed: false })} />;
  }
}

function PanelFallback({ onRetry }: { onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="bn-empty-state bn-route-error bn-panel-error" role="alert">
      <p>{t("labels.panelError")}</p>
      <button type="button" className="bn-btn bn-btn-primary" onClick={onRetry}>
        {t("buttons.retry")}
      </button>
    </div>
  );
}
