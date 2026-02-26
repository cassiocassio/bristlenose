/**
 * AppLayout — top-level layout for the report SPA.
 *
 * Renders the NavBar and an Outlet for the active route. Installs
 * backward-compat navigation shims on window for vanilla JS modules.
 */

import { useEffect } from "react";
import { Outlet, useNavigate } from "react-router-dom";
import { NavBar } from "../components/NavBar";
import { useScrollToAnchor } from "../hooks/useScrollToAnchor";
import { installNavigationShims } from "../shims/navigation";

export function AppLayout() {
  const navigate = useNavigate();
  const scrollToAnchor = useScrollToAnchor();

  useEffect(() => {
    installNavigationShims(navigate, scrollToAnchor);
  }, [navigate, scrollToAnchor]);

  return (
    <>
      <NavBar />
      <Outlet />
    </>
  );
}
