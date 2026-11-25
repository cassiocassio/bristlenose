"""The store-listing checker fires on what it claims to fire on.

A gate that cannot fail is not a gate, so each rule is shown to reject a mutated
listing and to pass the clean one.
"""

import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "check-store-listing.py"

FIELDS = {
    "name": "Bristlenose",
    "subtitle": "Research interview analysis",
    "promo": "Drop a folder of recordings. Get transcripts and quotes.",
    "keywords": "user research,interview,transcript,quotes",
    "desc": (
        "Drop in recordings and get quotes. It runs on your Mac. For the analysis, "
        "the interview text is sent to an AI provider you choose, using your own account: "
        "Claude, ChatGPT, Gemini or Azure OpenAI. The first run downloads a 1.5 GB model. It needs 10 GB of free space."
    ),
    "copyright": "2026 Someone",
    "marketing_url": "https://example.com",
    "privacy_url": "https://example.com/privacy.html",
    "support_url": "https://example.com/support.html",
    "review_notes": "Use the test key in Sign-in information. The app downloads a 1.5 GB model.",
    "captions": "One\nTwo\nThree",
    "iap_group_name": "Bristlenose",
    "iap_display_name": "Bristlenose Monthly",
    "iap_description": "Analyse new interview studies",
}


def run(tmp_path, **changes):
    fields = {**FIELDS, **changes}
    p = tmp_path / "listing.md"
    p.write_text("".join(f"## {k}\n\n{v}\n\n" for k, v in fields.items()), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(p)], capture_output=True, text=True, check=False
    )
    return r.returncode, r.stdout


def test_clean_listing_passes(tmp_path):
    code, out = run(tmp_path)
    assert code == 0, out


def test_size_figure_must_agree_between_desc_and_notes(tmp_path):
    code, out = run(tmp_path, review_notes="Use the test key. The app downloads a 1.6 GB model.")
    assert code == 1
    assert "download size differs" in out


def test_zoom_import_claim_is_allowed(tmp_path):
    # Zoom import shipped on for everyone on 19 Nov 2026; the old rule that
    # failed any description naming it (a Diagnostics beta then) is gone.
    code, out = run(tmp_path, desc=FIELDS["desc"] + " Import recordings from Zoom.")
    assert "Zoom import" not in out


def test_todo_in_a_field_fails(tmp_path):
    code, out = run(tmp_path, review_notes="Use the test key. TODO(owner): say more.")
    assert code == 1
    assert "still says TODO" in out


def test_free_space_figure_is_not_a_download_size(tmp_path):
    code, out = run(tmp_path, review_notes="Use the test key. The app downloads a 1.5 GB model.")
    assert code == 0, out


def test_miro_allowed_in_captions_but_not_in_subtitle(tmp_path):
    code, out = run(tmp_path, captions="One\nSend quotes to a Miro board\nThree")
    assert code == 0, out
    code, out = run(tmp_path, subtitle="Miro research analysis")
    assert code == 1
    assert "third-party names" in out

def test_figjam_allowed_in_captions_but_not_in_subtitle(tmp_path):
    code, out = run(tmp_path, captions="One\nSend to Miro, FigJam\nThree")
    assert code == 0, out
    code, out = run(tmp_path, subtitle="FigJam research analysis")
    assert code == 1
    assert "third-party names" in out


def test_import_services_allowed_in_captions_but_not_in_keywords(tmp_path):
    code, out = run(tmp_path, captions="One\nDirect from Teams, Google Meet and Zoom\nThree")
    assert code == 0, out
    code, out = run(tmp_path, keywords="zoom,teams,interview")
    assert code == 1
    assert "third-party names" in out


def test_subscription_text_must_fit_app_store_connect(tmp_path):
    # The plan name the paywall shows comes from this field, through the store.
    code, out = run(tmp_path, iap_display_name="B" * 36)
    assert code == 1
    assert "iap_display_name is 36/35 chars" in out
    code, out = run(tmp_path, iap_description="D" * 56)
    assert code == 1
    assert "iap_description is 56/55 chars" in out


def test_subscription_text_is_required(tmp_path):
    fields = {k: v for k, v in FIELDS.items() if k != "iap_display_name"}
    p = tmp_path / "listing.md"
    p.write_text("".join(f"## {k}\n\n{v}\n\n" for k, v in fields.items()), encoding="utf-8")
    r = subprocess.run(
        [sys.executable, str(SCRIPT), str(p)], capture_output=True, text=True, check=False
    )
    assert r.returncode == 1
    assert "field 'iap_display_name' is missing or empty" in r.stdout
