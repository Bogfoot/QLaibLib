"""Offline/mock acquisition backend for development and tests."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterable, Iterator, Sequence

import numpy as np

from .base import AcquisitionBackend
from ..data.models import AcquisitionBatch
from ..utils import timing


class MockBackend(AcquisitionBackend):
    def __init__(
        self,
        batches: Sequence[AcquisitionBatch] | None = None,
        *,
        channels: Sequence[int] = (1, 5, 2, 6, 3, 7, 4, 8),
        rate_hz: float = 8_000,
        exposure_sec: float = 1.0,
        rng_seed: int | None = None,
    ):
        self.default_exposure_sec = exposure_sec
        self._rng = np.random.default_rng(rng_seed)
        self._channels = tuple(channels)
        self._rate_hz = rate_hz
        if batches:
            self._iterator: Iterator[AcquisitionBatch] = itertools.cycle(batches)
        else:
            self._iterator = itertools.cycle(())

    def _synthetic_batch(self) -> AcquisitionBatch:
        singles = {}
        duration = self.default_exposure_sec
        for ch in self._channels:
            n = self._rng.poisson(self._rate_hz * duration)
            timestamps = np.sort(self._rng.uniform(0, duration * 1e12, size=n)).astype(
                np.int64
            )
            singles[ch] = timestamps
        return AcquisitionBatch(
            singles=singles,
            duration_sec=duration,
            started_at=timing.utc_now(),
            metadata={"mode": "synthetic"},
        )

    def capture(self, exposure_sec: float | None = None) -> AcquisitionBatch:
        exposure = exposure_sec or self.default_exposure_sec
        self.default_exposure_sec = exposure
        try:
            batch = next(self._iterator)
            return batch
        except StopIteration:
            self._iterator = itertools.cycle(())
        return self._synthetic_batch()
