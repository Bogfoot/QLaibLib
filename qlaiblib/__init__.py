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
from .coincidence.specs import DEFAULT_SPECS, DEFAULT_PAIRS, GHZ_TRIPLETS
from .data.models import AcquisitionBatch, CoincidenceSpec
from .live.controller import LiveAcquisition
from .live.tk_dashboard import run_dashboard
from .metrics import REGISTRY
from .acquisition.file_replay import FileReplayBackend

__all__ = [
    "QuTAGBackend",
    "MockBackend",
    "CoincidencePipeline",
    "CoincidenceSpec",
    "AcquisitionBatch",
    "DEFAULT_REF_PAIRS",
    "DEFAULT_CROSS_PAIRS",
    "FileReplayBackend",
    "DEFAULT_PAIRS",
    "GHZ_TRIPLETS",
    "DEFAULT_SPECS",
    "auto_calibrate_delays",
    "specs_from_delays",
    "LiveAcquisition",
    "run_dashboard",
    "REGISTRY",
]
