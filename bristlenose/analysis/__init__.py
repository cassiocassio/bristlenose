"""Analysis page computation — matrix building and signal detection."""

from bristlenose.analysis.generic_matrix import QuoteContribution, build_matrix_from_contributions
from bristlenose.analysis.generic_signals import QuoteRecord, detect_signals_generic
from bristlenose.analysis.models import AnalysisResult
from bristlenose.analysis.signals import detect_signals

__all__ = [
    "AnalysisResult",
    "QuoteContribution",
    "QuoteRecord",
    "build_matrix_from_contributions",
    "detect_signals",
    "detect_signals_generic",
]
