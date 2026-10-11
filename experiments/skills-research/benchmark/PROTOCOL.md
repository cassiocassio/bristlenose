# Review benchmark protocol (blind)

You are reviewing source files from a real product (Bristlenose: Python FastAPI/SQLAlchemy/SQLite pipeline + server, React/TS SPA, SwiftUI/AppKit sandboxed macOS app). Each case directory `bench/<CASE>/` holds:
- one or more source files, exactly as they stood at some commit;
- `FILES.txt` — the original repo paths of those files;
- `SCOPE.txt` — the enclosing function/type names of the region a reviewer should concentrate on (the area of a recent change). Review that region closely, using the rest of the file(s) and any `context/` files for understanding;
- optionally `context/` — supporting files from the same commit.

HARD RULES (the benchmark is void if broken):
1. Read ONLY files inside the case directories you are given. Do NOT open, grep, or git-query the live repository (`/Users/cassio/Code/bristlenose`), its docs, its tests, or its git history. Do not use the web.
2. Do not modify any file. Do not run the code.
3. Report what you genuinely believe is wrong (correctness, data loss, silent failure, races/ordering, security, error handling, UX-visible misbehaviour). Do not pad. Style nits only if nothing else.

OUTPUT: write a JSON file to the path you are given:
{"arm": "<arm>", "cases": {"<CASE>": [{"severity": "critical|high|medium|low", "title": "...", "location": "file:line or function", "explanation": "2-4 sentences: the defect, the concrete trigger, the consequence"}, ...]}}
Rank findings within a case by severity, max 6 per case. Then reply with just "done <path>".
