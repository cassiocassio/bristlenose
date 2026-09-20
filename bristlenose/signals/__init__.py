"""Signals computation — matrix building and signal detection."""

from bristlenose.signals.detect import detect_signals
from bristlenose.signals.generic_detect import QuoteRecord, detect_signals_generic
from bristlenose.signals.generic_matrix import QuoteContribution, build_matrix_from_contributions
from bristlenose.signals.models import SignalsResult

__all__ = [
    "SignalsResult",
    "QuoteContribution",
    "QuoteRecord",
    "build_matrix_from_contributions",
    "detect_signals",
    "detect_signals_generic",
]
