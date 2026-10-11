# Judge rubric

For each case you get: the answer key (`bench-keys/<CASE>/message.txt` = the real fix commit message; `fix.diff` = the real fix) and the buggy source (`bench/<CASE>/`). You are scoring anonymised reviewer outputs (labelled R1, R2, ...).

Per reviewer per case:
- **recall**: HIT = some finding names the actual root cause the fix addressed (mechanism, not just the function). PARTIAL = names the right region/symptom or a closely related mechanism but misses the operative cause, or names one of two real defects in a two-defect fix. MISS otherwise.
- **other findings**: for each finding that is NOT the key bug, classify by reading the buggy source: VALID (a real defect or a real risk a maintainer would act on), PLAUSIBLE (arguable/edge, defensible), WRONG (false — misreads the code, or claims behaviour the code does not have), NIT (style only). You may check the source to decide; be strict on WRONG.

Output JSON: {"<reviewer>": {"<CASE>": {"recall": "HIT|PARTIAL|MISS", "matching_finding": "<title or null>", "other": {"VALID": n, "PLAUSIBLE": n, "WRONG": n, "NIT": n}, "notes": "one line, esp. any notable VALID finding the real fix did not address"}}}
Be consistent across reviewers: identical claims get identical grades.
