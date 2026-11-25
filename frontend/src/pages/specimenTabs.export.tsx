import { Navigate } from "react-router-dom";

/**
 * Export-build stand-in for the dev specimen pages (`SpecimenTab`,
 * `PickerSpecimenTab`, `TagSpecimenTab`).
 *
 * `vite.export.config.ts` aliases each of those modules to this file, so the specimen
 * islands and their fixtures never enter the exported report's module graph
 * (a fixture there once shipped a real person's name inside every export).
 * Serve mode is untouched: the Mac Diagnostics menu still opens the real
 * pages. The routes stay registered and bounce to the report instead of 404ing.
 */
export function SpecimenTab() {
  return <Navigate to="/report/" replace />;
}

export function PickerSpecimenTab() {
  return <Navigate to="/report/" replace />;
}

export function TagSpecimenTab() {
  return <Navigate to="/report/" replace />;
}
