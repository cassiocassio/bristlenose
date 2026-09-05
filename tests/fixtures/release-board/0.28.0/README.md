# release-board fixture — the real 0.28.0 run

`events.jsonl`, `ci-sha` and `logs/` are the files `scripts/release.sh` wrote
during the 0.28.0 release (fail, retry, skip, resume, no `context.json`), copied
verbatim. `test-release-board.py::RealRun` asserts every tile against them.

**`steps.tbl` is reconstructed, not recorded.** The driver only began writing
`steps.tbl` into the run dir on 5 Sep 2026; 0.28.0 predates it. The copy here
was synthesised from `run_steps` as it stood on that date, so the fixture
exercises the steps.tbl path (station order, tiers, kinds) rather than the
ledger-order fallback. Two consequences: the file is a claim about what the
driver *would* have declared, and the fallback path is covered by
`test_no_steps_tbl_falls_back_to_ledger_order_and_says_so`, not by this run.
There is no `bn-events.log`: the sink did not exist either, so every lane
reads `ran-no-sink` and the preflight pane `no-data` — the fixture's value is
the ledger fold, not the feed.
