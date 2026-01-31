"""Tests for PII default behaviour: off by default, opt-in with --redact-pii."""

from bristlenose.config import BristlenoseSettings


def test_pii_default_is_false() -> None:
    """PII redaction should be disabled by default."""
    settings = BristlenoseSettings()
    assert settings.pii_enabled is False


def test_pii_override_true() -> None:
    """PII redaction can be explicitly enabled."""
    settings = BristlenoseSettings(pii_enabled=True)
    assert settings.pii_enabled is True


def test_pii_override_false_explicit() -> None:
    """PII redaction can be explicitly disabled (redundant but valid)."""
    settings = BristlenoseSettings(pii_enabled=False)
    assert settings.pii_enabled is False
