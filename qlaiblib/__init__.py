"""QLaibLib public API."""

from .acquisition.qutag import QuTAGBackend
from .acquisition.mock import MockBackend
from .coincidence.pipeline import CoincidencePipeline
from .coincidence.delays import (
    DEFAULT_REF_PAIRS,
    DEFAULT_CROSS_PAIRS,
    auto_calibrate_delays,
    specs_from_delays,
)
from .data.models import AcquisitionBatch, CoincidenceSpec
from .live.controller import LiveAcquisition
from .live.tk_dashboard import run_dashboard
from .metrics import REGISTRY

__all__ = [
    "QuTAGBackend",
    "MockBackend",
    "CoincidencePipeline",
    "CoincidenceSpec",
    "AcquisitionBatch",
    "DEFAULT_REF_PAIRS",
    "DEFAULT_CROSS_PAIRS",
    "auto_calibrate_delays",
    "specs_from_delays",
    "LiveAcquisition",
    "run_dashboard",
    "REGISTRY",
]
