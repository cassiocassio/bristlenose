"""The download job waits out a network that comes back, and gives up on nothing else.

hf_xet does not resume and a download dies with its connection: on macOS 15 and 26 guests an
outage of 12 s was survived and one of 18 s ended a 1.6 GB fetch (30 Oct 2026), after which
Retry restarted from zero. A laptop changing Wi-Fi, waking, or reconnecting a VPN does that
routinely, so the job now waits for the Hub and starts again by itself, a bounded number of
times, for failures a returning network can cure and for no others.
"""

from __future__ import annotations

import pytest

from bristlenose.config import BristlenoseSettings
from bristlenose.preflight import whisper
from bristlenose.utils.package_install import PackageInstallError

REPO = "mlx-community/whisper-large-v3-turbo"

DNS = "huggingface_hub snapshot_download 'x' failed: [Errno 8] nodename nor servname provided, or not known"
CONNECT = "huggingface_hub snapshot_download 'x' failed: Got: ConnectError: [Errno 61] Connection refused"
RESET = "huggingface_hub snapshot_download 'x' failed: Got: ReadError: [Errno 54] Connection reset by peer"
TIMEOUT = "huggingface_hub snapshot_download 'x' failed: The read operation timed out"


HUB_BUSY = "huggingface_hub snapshot_download 'x' failed: 429 Client Error: Too Many Requests for url"
HUB_DOWN = "huggingface_hub snapshot_download 'x' failed: 503 Server Error: Service Unavailable"
OFFLINE_START = "The cached snapshot for 'x' (revision 'main', commit a4aaeec) is incomplete: 1 file(s) are missing"


@pytest.mark.parametrize("text", [DNS, RESET, TIMEOUT, HUB_BUSY, HUB_DOWN, OFFLINE_START])
def test_failures_a_returning_network_cures_are_recognised(text: str) -> None:
    assert whisper.is_network_failure(PackageInstallError(text))


@pytest.mark.parametrize(
    "text",
    [
        "snapshot_download 'x' failed: [Errno 28] No space left on device",
        "snapshot_download 'x' failed: [Errno 13] Permission denied: '/Users/a/ro/hf'",
        "snapshot_download 'x' failed: Got: ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed",
        "snapshot_download 'x' failed: 401 Client Error: Unauthorized",
        "snapshot_download 'x' failed: [Errno 25] Inappropriate ioctl for device",
        CONNECT,  # refused: a dead proxy or firewall answers at once; waiting does not cure it
        # An I/O error naming a ".incomplete" file is a disk problem, not a network one.
        "snapshot_download 'x' failed: [Errno 5] Input/output error: '/Volumes/D/blobs/ab.incomplete'",
    ],
)
def test_failures_waiting_cannot_cure_are_not_retried(text: str) -> None:
    assert not whisper.is_network_failure(PackageInstallError(text))


def test_a_certificate_failure_is_not_mistaken_for_a_network_one_by_its_connecterror_prefix() -> None:
    """It arrives wrapped in 'ConnectError', a network word; the certificate wins."""
    assert not whisper.is_network_failure(
        PackageInstallError("Got: ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] self-signed")
    )


class _Job:
    """A fake model fetch: fails with the given messages in turn, then succeeds."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, failures: list[str]) -> None:
        self.failures = list(failures)
        self.calls = 0
        self.lines: list[str] = []
        self.slept: list[float] = []
        self.cached = False
        monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
        monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: REPO)
        monkeypatch.setattr(whisper, "cache_state", lambda _r: "cached" if self.cached else "missing")
        monkeypatch.setattr(whisper, "_server_total_bytes", lambda _r: 1000)
        monkeypatch.setattr(whisper, "ensure_disk_room", lambda _r: None)
        monkeypatch.setattr(whisper, "discard_stale_partials", lambda *_a, **_k: 0)
        monkeypatch.setattr(whisper, "_retry_sleep", self.slept.append)
        monkeypatch.setattr(whisper, "_wait_until_reachable", lambda *_a, **_k: 1000)
        monkeypatch.setattr("bristlenose.utils.package_install.ensure_hf_model", self.fetch)

    def fetch(self, *_a: object, **_k: object) -> None:
        self.calls += 1
        if self.failures:
            raise PackageInstallError(self.failures.pop(0))
        self.cached = True

    def run(self) -> None:
        whisper.fetch_with_progress_lines(BristlenoseSettings(), write=self.lines.append)


def test_a_dropped_connection_is_waited_out_and_the_fetch_starts_again(monkeypatch) -> None:
    job = _Job(monkeypatch, [DNS, RESET])
    job.run()
    assert job.calls == 3
    assert job.lines[-1].startswith("@download-done")
    # start, then one reset per restart (the pill goes back to zero), then the forced final line
    assert job.lines[0].startswith("@download-start")
    assert job.lines[1:3] == ["@download 0 1000", "@download 0 1000"]


def test_a_failure_waiting_cannot_cure_is_raised_at_once(monkeypatch) -> None:
    job = _Job(monkeypatch, ["failed: [Errno 28] No space left on device"])
    with pytest.raises(PackageInstallError, match="No space"):
        job.run()
    assert job.calls == 1


def test_it_gives_up_after_the_bounded_number_of_restarts(monkeypatch) -> None:
    job = _Job(monkeypatch, [DNS] * 20)
    with pytest.raises(PackageInstallError):
        job.run()
    assert job.calls == whisper._NETWORK_RETRY_ATTEMPTS + 1


def test_a_hub_that_never_answers_gives_the_failure_back(monkeypatch) -> None:
    job = _Job(monkeypatch, [DNS] * 3)
    monkeypatch.setattr(whisper, "_wait_until_reachable", lambda *_a, **_k: 0)
    with pytest.raises(PackageInstallError, match="nodename"):
        job.run()
    assert job.calls == 1


def test_stop_during_a_wait_is_not_swallowed(monkeypatch) -> None:
    """SIGINT in the app's Stop raises KeyboardInterrupt inside the wait; it must get out."""
    job = _Job(monkeypatch, [DNS])

    def interrupted(*_a: object, **_k: object) -> int:
        raise KeyboardInterrupt

    monkeypatch.setattr(whisper, "_wait_until_reachable", interrupted)
    with pytest.raises(KeyboardInterrupt):
        job.run()


class _Clock:
    """A clock the test moves: sleeping advances it, and so does a slow question."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, ask_takes_s: float = 0.0) -> None:
        self.now = 0.0
        self.asks = 0
        self.ask_takes_s = ask_takes_s
        monkeypatch.setattr(whisper, "_retry_clock", lambda: self.now)
        monkeypatch.setattr(whisper, "_retry_sleep", self.sleep)

    def sleep(self, secs: float) -> None:
        self.now += secs

    def ask(self, answers: list[int]):
        def _ask(_repo: str, **_kw: object) -> int:
            self.asks += 1
            self.now += self.ask_takes_s
            return answers.pop(0) if answers else 0

        return _ask


def test_waiting_polls_the_hub_until_it_answers_and_returns_its_size(monkeypatch) -> None:
    clock = _Clock(monkeypatch)
    monkeypatch.setattr(whisper, "_server_total_bytes", clock.ask([0, 0, 0, 1234]))
    assert whisper._wait_until_reachable(REPO, wait_s=60) == 1234
    assert clock.now == 5.0 + 7.5 + 11.25, "the gap between questions grows"


def test_waiting_stops_at_the_limit_and_reports_no_answer(monkeypatch) -> None:
    clock = _Clock(monkeypatch)
    monkeypatch.setattr(whisper, "_server_total_bytes", clock.ask([]))
    assert whisper._wait_until_reachable(REPO, wait_s=20) == 0
    assert clock.now >= 20


def test_the_limit_is_wall_time_so_slow_questions_cannot_stretch_it(monkeypatch) -> None:
    """A network that drops packets makes each question slow. Counting sleeps would let 60 of
    them run for an hour; the clock stops it."""
    clock = _Clock(monkeypatch, ask_takes_s=10.0)
    monkeypatch.setattr(whisper, "_server_total_bytes", clock.ask([]))
    assert whisper._wait_until_reachable(REPO, wait_s=60) == 0
    assert clock.now < 60 + 10 + whisper._NETWORK_POLL_S  # one question past the limit at most
    assert clock.asks <= 6


def test_a_question_to_the_hub_has_a_timeout(monkeypatch) -> None:
    """huggingface_hub's default is none at all."""
    seen: dict[str, object] = {}

    class FakeApi:
        def model_info(self, repo_id: str, **kwargs: object):
            seen.update(kwargs)
            raise OSError("no route")

    monkeypatch.setattr("huggingface_hub.HfApi", FakeApi)
    assert whisper._server_total_bytes(REPO, log_failure=False) == 0
    assert seen["timeout"] == whisper._HUB_ASK_TIMEOUT_S


def test_the_size_the_wait_just_fetched_replaces_a_total_an_offline_start_never_had(
    monkeypatch,
) -> None:
    job = _Job(monkeypatch, [OFFLINE_START])
    monkeypatch.setattr(whisper, "_server_total_bytes", lambda _r, **_k: 0)  # offline at start
    monkeypatch.setattr(whisper, "_wait_until_reachable", lambda *_a, **_k: 1614)
    job.run()
    assert job.lines[0] == f"@download-start {REPO} 0"
    assert "@download 0 1614" in job.lines, "the pill learns the size once the Hub answers"


def test_a_hub_that_is_up_but_refusing_is_not_hammered(monkeypatch) -> None:
    job = _Job(monkeypatch, [HUB_BUSY, HUB_BUSY])
    job.run()
    assert job.slept == [5.0, 10.0], "backs off 5 s, then 10 s, between restarts"


# ── hf_xet is Rust: its failures read differently from Python's ─────────────────────────────


@pytest.mark.parametrize(
    "text",
    [
        "snapshot_download 'x' failed: error sending request for url (https://cas-bridge.xethub.hf.co/x)",
        "snapshot_download 'x' failed: connection closed before message completed",
        "snapshot_download 'x' failed: error decoding response body",
        "snapshot_download 'x' failed: dns error: failed to lookup address information",
        "snapshot_download 'x' failed: Connection reset by peer (os error 54)",
        "snapshot_download 'x' failed: operation timed out (os error 60)",
    ],
)
def test_the_rust_downloaders_own_wording_is_recognised(text: str) -> None:
    assert whisper.is_network_failure(PackageInstallError(text))


def test_a_stream_cut_mid_transfer_on_the_plain_http_path_is_an_outage_not_a_certificate() -> None:
    """httpx/OpenSSL words a cut connection as an SSL error; only a certificate failure is not one."""
    assert whisper.is_network_failure(
        PackageInstallError("ReadError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol")
    )
    assert not whisper.is_network_failure(
        PackageInstallError("ConnectError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed")
    )


def test_a_rust_certificate_failure_is_still_not_a_network_one() -> None:
    assert not whisper.is_network_failure(
        PackageInstallError("error sending request for url (https://x): invalid peer certificate: UnknownIssuer")
    )


def test_resource_temporarily_unavailable_is_not_an_outage() -> None:
    """EAGAIN. 'temporarily unavailable' alone would wait five minutes for a cure that cannot come."""
    assert not whisper.is_network_failure(
        PackageInstallError("snapshot_download 'x' failed: [Errno 35] Resource temporarily unavailable")
    )


def test_offline_on_purpose_is_not_waited_out(monkeypatch) -> None:
    """HF_HUB_OFFLINE=1 turns a failed fetch into 'cached snapshot ... incomplete', which is the
    answer the user asked for, not an outage."""
    monkeypatch.setenv("HF_HUB_OFFLINE", "1")
    assert not whisper.is_network_failure(PackageInstallError(OFFLINE_START))


# ── the same loop on the terminal path ────────────────────────────────────────────────────


def test_a_terminal_run_waits_out_a_dropped_network_too(monkeypatch) -> None:
    from rich.console import Console

    monkeypatch.delenv("BRISTLENOSE_SKIP_PREFLIGHT", raising=False)
    monkeypatch.delenv("_BRISTLENOSE_WHISPER_FETCH_PID", raising=False)
    monkeypatch.setattr(whisper, "unknown_model_message", lambda _s: None)
    monkeypatch.setattr(whisper, "_resolve_repo_id", lambda _s: REPO)
    monkeypatch.setattr(whisper, "cache_state", lambda _r: "missing")
    monkeypatch.setattr(whisper, "_print_banner", lambda *_a: None)
    monkeypatch.setattr(whisper, "_stderr_is_tty", lambda: True)
    monkeypatch.setattr(whisper, "ensure_disk_room", lambda _r: None)
    monkeypatch.setattr(whisper, "discard_stale_partials", lambda *_a, **_k: 0)
    monkeypatch.setattr(whisper, "_retry_sleep", lambda _s: None)
    monkeypatch.setattr(whisper, "_wait_until_reachable", lambda *_a, **_k: 1000)
    calls: list[int] = []

    def fetch(*_a: object, **_k: object) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise PackageInstallError(DNS)

    monkeypatch.setattr("bristlenose.utils.package_install.ensure_hf_model", fetch)
    console = Console(record=True, width=120)
    whisper.preflight_whisper(
        settings=BristlenoseSettings(), console=console, status=None, allow_fetch=True
    )
    assert len(calls) == 2
    said = console.export_text().lower()
    assert "network dropped" in said, "says it is waiting"
    assert "network is back" in said, "and says when it starts again, so the wait is not mistaken for a hang"


# ── a live writer's file is not taken, however quiet it has gone ──────────────────────────


def _repo_with_blobs(monkeypatch: pytest.MonkeyPatch, tmp_path):
    hub = tmp_path / "hub"
    repo = hub / "models--mlx-community--whisper-large-v3-turbo"
    (repo / "blobs").mkdir(parents=True)
    monkeypatch.setattr(whisper, "_repo_cache_dir", lambda _r: repo)
    return hub, repo


def _old(path, size: int = 5000) -> None:
    import os
    import time

    path.write_bytes(b"x" * size)
    t = time.time() - 3600
    os.utime(path, (t, t))


def test_a_partial_whose_download_lock_is_held_survives_however_old(monkeypatch, tmp_path) -> None:
    """hf_xet rides out ~15 s of silence and a SIGSTOPped or sleeping writer touches nothing:
    mtime is no witness. huggingface_hub holds a FileLock for the whole download; that is.

    The holder is the Hub's own lock class (flock on POSIX, a byte-range lock on Windows),
    so this runs wherever the Hub downloads; a raw fcntl.flock here could not."""
    from filelock import FileLock

    hub, repo = _repo_with_blobs(monkeypatch, tmp_path)
    _old(repo / "blobs" / "abc123.deadbeef.incomplete")
    lockdir = hub / ".locks" / repo.name
    lockdir.mkdir(parents=True)
    holder = FileLock(str(lockdir / "abc123.lock"))
    holder.acquire()
    try:
        assert whisper.discard_stale_partials(REPO, min_age_s=0) == 0
        assert (repo / "blobs" / "abc123.deadbeef.incomplete").exists()
    finally:
        holder.release()
    # Released: now it is an orphan like any other.
    assert whisper.discard_stale_partials(REPO, min_age_s=0) == 5000


def test_a_partial_with_no_lock_file_is_an_orphan(monkeypatch, tmp_path) -> None:
    _hub, repo = _repo_with_blobs(monkeypatch, tmp_path)
    _old(repo / "blobs" / "abc123.deadbeef.incomplete")
    assert whisper.discard_stale_partials(REPO, min_age_s=0) == 5000


def test_the_backoff_comes_before_the_wait_for_the_hub(monkeypatch) -> None:
    """A Hub that is up but refusing answers the wait's first question at once, so the spacing
    between restarts has to come first (swapping the two lines used to pass every test)."""
    job = _Job(monkeypatch, [HUB_BUSY])
    order: list[str] = []
    monkeypatch.setattr(whisper, "_retry_sleep", lambda s: order.append(f"sleep {s:g}"))
    monkeypatch.setattr(whisper, "_wait_until_reachable", lambda *_a, **_k: order.append("wait") or 1000)
    job.run()
    assert order == ["sleep 5", "wait"]
