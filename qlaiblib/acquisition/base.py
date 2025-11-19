"""Acquisition backend interfaces."""

from __future__ import annotations

import abc
from typing import Iterable

from ..data.models import AcquisitionBatch


class AcquisitionBackend(abc.ABC):
    """Abstract base class for hardware-specific acquisition."""

    default_exposure_sec: float = 1.0

    @abc.abstractmethod
    def capture(self, exposure_sec: float | None = None) -> AcquisitionBatch:
        """Capture a chunk of singles with the selected exposure time."""

    def stream(self, *, exposure_sec: float | None = None) -> Iterable[AcquisitionBatch]:
        while True:
            yield self.capture(exposure_sec)

    def close(self) -> None:  # pragma: no cover - optional override
        """Release hardware resources."""

    def __enter__(self):  # pragma: no cover - context convenience
        return self

    def __exit__(self, exc_type, exc, tb):  # pragma: no cover - context convenience
        self.close()
        return False
