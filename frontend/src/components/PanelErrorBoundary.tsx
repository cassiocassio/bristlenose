import { Component, type ReactNode } from "react";
import { useInRouterContext, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { Icon } from "./Icon";

/**
 * Error boundary for one part of the report around the lens (R85). A part that
 * throws while rendering shows a short message where it was, instead of
 * reaching the `/report` route boundary and blanking the whole report. The
 * lens and the other parts keep working.
 *
 * Two uses. `SidebarLayout` wraps the side panels: the left panel and the tag
 * sidebar say "This sidebar couldn’t be shown", and the minimap is `quiet`.
 * `AppLayout` and the modals wrap the chrome, with `part`: the header and nav
 * in their bar's slot, and each modal's content inside its own `.bn-modal`, so
 * the overlay, the × and Escape, which the modal owns, still close it. The
 * footer, the activity chips and the invisible syncs are `quiet`.
 *
 * A `part` fallback is a glyph, not words (owner, 20 Oct 2026): the
 * broken-image mark, drawn quietly in the muted colour, with no button. Words
 * read as content or navigation and have to be parsed; a broken mark reads as
 * broken, can be ignored if the rest of the report works, and carries the
 * remedy everyone already knows, reload: the browser's own, or View ▸ Reload
 * Report (⌘R) and right-click ▸ Reload Report in the Mac app. It is not an
 * alert; assistive technology meets it as an image named "This couldn’t be
 * shown." (`labels.partError`).
 *
 * A boundary catches only what renders below it, and a modal's content is
 * inline JSX evaluated in the modal's own render, above anything it wraps. So
 * the content may be passed as a function: it is then called inside the
 * boundary (by `Deferred`), and a throw in it is caught here. A throw in the
 * modal's own body (its hooks, or a value it computes before returning) is
 * still above the boundary and blanks the report; keep that body small.
 *
 * A sidebar's Retry remounts it, which refetches whatever it reads; choosing
 * another lens (any route change) clears any of these fallbacks too, the same
 * way React Router clears the per-lens boundary. `quiet` renders nothing instead of a
 * message, where a message would be noise or there is no room for one.
 *
 * As with RouteError, the error is logged to the console, never shown. Every
 * fallback carries `bn-route-error` too, so the sidebar one takes the same
 * button spacing and the e2e crash check (`.bn-route-error`) sees any of them.
 */
export function PanelErrorBoundary({
  children,
  quiet = false,
  part = false,
}: {
  children: ReactNode | (() => ReactNode);
  quiet?: boolean;
  part?: boolean;
}) {
  // SidebarLayout is also mounted without a router (its own unit tests), so the
  // route-change reset is read only when there is one.
  return useInRouterContext() ? (
    <ResetOnRouteChange quiet={quiet} part={part}>{children}</ResetOnRouteChange>
  ) : (
    <Boundary quiet={quiet} part={part}>{children}</Boundary>
  );
}

function ResetOnRouteChange({ children, quiet, part }: Omit<BoundaryProps, "resetKey">) {
  const { pathname } = useLocation();
  return (
    <Boundary quiet={quiet} part={part} resetKey={pathname}>
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
    if (this.props.part) return <PartFallback />;
    return <PanelFallback onRetry={() => this.setState({ failed: false })} />;
  }
}

/** The broken mark where the part was: no words, no button, not an alert. */
function PartFallback() {
  const { t } = useTranslation();
  return (
    <div className="bn-route-error bn-part-error">
      <Icon name="broken" label={t("labels.partError")} />
    </div>
  );
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
