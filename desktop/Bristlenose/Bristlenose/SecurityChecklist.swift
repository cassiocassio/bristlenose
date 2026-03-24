// SecurityChecklist.swift — compile-time guard against shipping unfixed security issues.
//
// Each item below maps to the pre-distribution security audit (CLAUDE.md / design-desktop-app.md).
// In DEBUG builds these are warnings (yellow — visible but non-blocking).
// In RELEASE builds these are errors (red — cannot archive or export).
//
// When you fix an item, delete its #warning/#error pair entirely.
// When every item is gone, delete this file.

#if DEBUG

#warning("SECURITY #1: Unauthenticated localhost API — add per-session bearer token, inject into WKWebView")
#warning("SECURITY #2: /media mount exposes entire project dir — add extension allowlist in FastAPI")
#warning("SECURITY #3: CORS middleware missing — add CORSMiddleware to FastAPI app")
#warning("SECURITY #5: Zombie cleanup kills any PID on 8150-9149 — verify process is bristlenose before kill()")
#warning("SECURITY #7: Full ProcessInfo.environment inherited by sidecar — construct minimal env")
#warning("SECURITY #8: Navigation policy allows any localhost port — restrict to expected serve port")

#else

#error("SECURITY #1: Unauthenticated localhost API — add per-session bearer token, inject into WKWebView")
#error("SECURITY #2: /media mount exposes entire project dir — add extension allowlist in FastAPI")
#error("SECURITY #3: CORS middleware missing — add CORSMiddleware to FastAPI app")
#error("SECURITY #5: Zombie cleanup kills any PID on 8150-9149 — verify process is bristlenose before kill()")
#error("SECURITY #7: Full ProcessInfo.environment inherited by sidecar — construct minimal env")
#error("SECURITY #8: Navigation policy allows any localhost port — restrict to expected serve port")

#endif
