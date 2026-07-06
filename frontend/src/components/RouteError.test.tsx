import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { RouteError } from "./RouteError";

// The invariant: when a route throws during render, the user sees a calm
// fallback (a message + a retry control) — never a white screen, and never
// the raw error text.

function Boom(): never {
  throw new Error("kaboom-secret-stack-detail");
}

describe("RouteError", () => {
  beforeEach(() => {
    // React Router logs caught errors to console.error; silence for the assertion.
    vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders a fallback instead of crashing when a route throws", () => {
    const router = createMemoryRouter(
      [{ path: "/", element: <Boom />, errorElement: <RouteError /> }],
      { initialEntries: ["/"] },
    );
    render(<RouterProvider router={router} />);

    // Fallback is shown, with an alert role and a retry affordance.
    expect(screen.getByRole("alert")).toBeTruthy();
    expect(screen.getByRole("button", { name: /retry/i })).toBeTruthy();
  });

  it("does not surface the raw error message to the user", () => {
    const router = createMemoryRouter(
      [{ path: "/", element: <Boom />, errorElement: <RouteError /> }],
      { initialEntries: ["/"] },
    );
    render(<RouterProvider router={router} />);

    expect(screen.queryByText(/kaboom-secret-stack-detail/)).toBeNull();
  });
});
