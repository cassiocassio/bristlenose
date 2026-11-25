# Design System Reference

Reference docs for contributors working on the Bristlenose UI.

- **The style guide is a page in the app, `/report/style-guide`** (`frontend/src/islands/StyleGuide.tsx`; Diagnostics ▸ Style Guide on the Mac). Every example is drawn by the shipped React components and the loaded theme CSS on fixture data, across Default and Edo, light and dark, web and desktop type. Sections are CSF modules in `frontend/src/islands/styleGuide/`. Tags are on `/report/tag-specimen`. **style-guide.html** is now a stub pointing there: its hand-copied CSS drifted from the app (25 Nov 2026).
- **icon-catalog.html** — current icon usage and candidates for the SVG icon set migration
- **compliance-catalogue.html** — the token X-ray: every component CSS file scored for how much of it flows through `--bn-*` tokens, specimens in all four theme combinations, an X-ray toggle that outlines what sits outside the system, and an on-screen panel from the running app. Generated: rebuild with `.venv/bin/python scripts/build-compliance-catalogue.py` (specimen markup and hand-written fix wording live in `compliance-specimens.json`). The scoring is `scripts/audit-css.py`; the on-screen scan is `experiments/token-xray/live-scan.mjs --all`.
