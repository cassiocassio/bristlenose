# Release timing and post-push PyPI verification

Moved verbatim from the root `CLAUDE.md` on 5 Nov 2026 to cut what every session loads on every turn. The root keeps a short rule and a pointer here.

### Release timing (evening releases)

Releases land after 9pm London on a **working day**; **the act that lands a
release is the tag push.** Weekends and **UK bank holidays: any time** — the
rule exists to keep release notifications out of client working hours, and on a
day when clients are not working there is nothing to keep them out of. The `pypi` environment's required-reviewer hold was **removed on
23 Aug 2026** — it had been the reason the tag could go out early, because a
tagged run then waited for a human before publishing.

**Why it went.** At the approval moment every fact is mechanical: both CI runs,
the artefact's signature and staple, `tag == HEAD`, the version not already on
PyPI. A human clicking Approve at 11pm re-verifies none of them. The click was
a second asking of a question already answered by typing "release" — and at
**97 releases in 204 days** that ceremony was expensive and the judgement empty.

**Removing the hold did not remove the gate.** `publish` needs `build` needs
`ci`, and `release.yml` invokes `ci.yml` with `strict-macos: true`. PyPI cannot
receive a version whose full matrix, e2e and strict macOS suite did not pass on
the tagged commit. `check-release-ready.sh`'s `publish gate` row asserts that
chain and **fails** if it is ever broken — the click became assertions that
actually inspect the artefact.

Consequences:

1. Push `main` **any time** — it never publishes and it buys CI signal.
2. **The tag goes LAST**, after the Mac uploads and after a strict CI verdict on
   `main`. `ci.yml` exposes `strict-macos` on `workflow_dispatch`, so the strict
   verdict is obtainable without a tag — which is what preserves the 0.25.2
   lesson (every verdict before every irreversible act) now that the tag is the
   publishing act. `./scripts/release.sh run` encodes this order.
3. **The tag push is what waits for 9pm — on working days only.** Weekends and
   UK bank holidays: any time. Still two back-to-back commands, never one
   `--tags` — the bundled push is how the tag-driven workflow gets debounced
   into never firing.

   **Check the holiday, don't derive it.** The UK government publishes the
   official list, so this is one command and never a calculation:

   ```bash
   curl -s https://www.gov.uk/bank-holidays.json | jq -r --arg d "$(date +%F)" '."england-and-wales".events[] | select(.date==$d) | .title'
   ```

   Non-empty output is the answer — today is that holiday, so the window is
   open now. Added 31 Aug 2026, when a release was scheduled to wait until 9pm
   on the **Summer bank holiday**: "is it a weekday" was answered by `date +%u`,
   which returns 1 for a Monday whether or not anyone is working. Reasoning it
   out from "last Monday in August" is the same mistake one step later — the
   division is *working day*, and England-and-Wales, Scotland and Northern
   Ireland do not share a calendar, which is exactly why the feed is keyed by
   nation.

**Override:** push when something is urgent. This is a guideline, not a gate.

**A running release freezes `main`, locally.** While a `release.sh run` driver is
alive, the `release-freeze` pre-commit hook refuses commits in this checkout and
its worktrees (not pushes of earlier commits, `--no-verify`, or other machines,
and not the gap after a failed step, when a fix is supposed to land):
a commit then would move HEAD under the release, forcing a rebuild and a fresh
strict-CI run, and could change what ships (0.34.0 was planned as 0.33.1 and
became a minor that way). The release's own commits pass; a fix the release
needs goes in with `BN_RELEASE_FREEZE_OK=1 git commit …`. **Work that must not
go live before the new version is on PyPI** (an install guide naming it, a
one-liner that installs it) waits on a branch named `after-pypi/<version>`.
The same holds for any channel: `after-<channel>/<version>[-anything]`
(`after-winget/0.36.0` holds the docs that make winget the lead Windows route),
in this repo or the website's. `release.sh verify` lists every hold in both
repos with `land`, `wait` or `?` per channel. It lands a hold when that channel
carries the version or a later one, without waiting for every channel to
verify, and reports a misnamed `after-*` branch rather than skipping it.

**Why:** avoids release notifications during client working hours; batches
releases into a predictable window. Both halves of that purpose are about *when
other people are at work*, which is the test to apply when a new edge case turns
up — not the shape of the calendar.

### Post-push PyPI verification (mandatory)

A tag push that reaches GitHub is NOT the same as a release that reaches PyPI. The release pipeline silently stalled from v0.15.5 to v0.15.9 (five versions, ~6 days) because no step checked that PyPI actually accepted the upload. **After pushing the tag, verify before declaring the release done:**

```sh
for i in $(seq 1 20); do
  sleep 90
  pypi=$(curl -s https://pypi.org/pypi/bristlenose/json | jq -r .info.version)
  echo "[$i] PyPI: $pypi"
  [ "$pypi" = "<X.Y.Z>" ] && break
done
```

20 iterations × 90s = 30 minutes. Recent releases have run 23–25 minutes (v0.15.13: 25m41s, v0.15.14: 23m22s); the original 15-minute budget routinely expired during a normal release. **v0.23.0 took ~2 hours across three attempts** — budget generously on a release that touches the test suite. If PyPI still reports the previous version after 30 minutes: `gh run view --workflow=release.yml` to check the workflow fired. Apply the v0.15.0 debouncing workaround (`git push --delete origin v<X.Y.Z> && git push origin v<X.Y.Z>`) if it didn't.

**`/pypi/<pkg>/json` is CDN-cached and CAN read stale — don't trust a single negative.** During the v0.23.0 verification the poll returned `0.23.0`, and a re-check seconds later returned `0.22.0` from a different edge node. A stale read looks exactly like "the release never published" and would send you into unnecessary tag surgery on an already-successful run. **Confirm with the version-specific endpoint**, which is authoritative and unambiguous:

```sh
curl -s -o /dev/null -w '%{http_code}\n' https://pypi.org/pypi/bristlenose/<X.Y.Z>/json   # 200 = published
```

A cache-busted index (`?cb=$RANDOM` + `Cache-Control: no-cache`) is the second check; `releases["<X.Y.Z>"]` should hold 2 files (sdist + wheel). Check `gh run view <id> --json conclusion` too — a `success` conclusion plus a 200 on the version URL means published, whatever the cached index says.
