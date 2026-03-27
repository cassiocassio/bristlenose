// SecurityChecklist.swift — compile-time guard against shipping unfixed security issues.
//
// Each item below maps to the pre-distribution security audit (CLAUDE.md / design-desktop-app.md).
// In DEBUG builds these are warnings (yellow — visible but non-blocking).
// In RELEASE builds these are errors (red — cannot archive or export).
//
// When you fix an item, delete its #warning/#error pair entirely.
// When every item is gone, delete this file.
//
// Resolved (removed):
//   #1 Bearer token — implemented in ServeManager + WebView (v0.14.0)
//   #2 Media allowlist — implemented in FastAPI (v0.14.0)
//   #3 CORS middleware — implemented in FastAPI (v0.14.0)
//   #7 Env scrubbing — implemented in ServeManager (v0.14.0)

#if DEBUG

#warning("SECURITY #5: Zombie cleanup kills any PID on 8150-9149 — verify process is bristlenose before kill()")
#warning("SECURITY #8: Navigation policy allows any localhost port — restrict to expected serve port")

#else

#error("SECURITY #5: Zombie cleanup kills any PID on 8150-9149 — verify process is bristlenose before kill()")
#error("SECURITY #8: Navigation policy allows any localhost port — restrict to expected serve port")

#endif
