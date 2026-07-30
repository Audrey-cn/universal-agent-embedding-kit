"""Effort Dispatch Engine — Effort 调度引擎"""

from .cache import (
    EffortCache,
    classify_with_cache,
    get_global_cache,
    record_classification_feedback,
)
from .classifier import EffortClassifier
from .dispatch_phrases import get_dispatch_phrase
from .interface import EffortLevel, EffortResult, classify
from .metrics import ComplexityMetrics
from .verification_depth import get_verification_depth

__all__ = [
    "EffortLevel",
    "EffortResult",
    "classify",
    "ComplexityMetrics",
    "EffortClassifier",
    "EffortCache",
    "classify_with_cache",
    "get_global_cache",
    "record_classification_feedback",
    "get_dispatch_phrase",
    "get_verification_depth",
]
