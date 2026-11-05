# Design System Reference

Reference docs for contributors working on the Bristlenose UI.

- **style-guide.html** — visual inventory of design tokens, typography, colours, spacing
- **icon-catalog.html** — current icon usage and candidates for the SVG icon set migration
- **compliance-catalogue.html** — the token X-ray: every component CSS file scored for how much of it flows through `--bn-*` tokens, specimens in all four theme combinations, an X-ray toggle that outlines what sits outside the system, and an on-screen panel from the running app. Generated: rebuild with `.venv/bin/python scripts/build-compliance-catalogue.py` (specimen markup and hand-written fix wording live in `compliance-specimens.json`). The scoring is `scripts/audit-css.py`; the on-screen scan is `experiments/token-xray/live-scan.mjs --all`.
