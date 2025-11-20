"""Replay BIN/CSV files as if they were live acquisitions."""

from __future__ import annotations

import itertools
from pathlib import Path
from typing import Iterator

import numpy as np

from ..data.models import AcquisitionBatch
from ..io import coincfinder_backend as cf_backend
from ..utils import timing
from .base import AcquisitionBackend


class FileReplayBackend(AcquisitionBackend):
    """Yield chunks from a prerecorded BIN/CSV file at fixed exposure intervals."""

    def __init__(
        self,
        path: str | Path,
        *,
        exposure_sec: float,
        bucket_seconds: float | None = None,
        loop: bool = True,
    ) -> None:
        self.path = Path(path)
        self.default_exposure_sec = exposure_sec
        self.bucket_seconds = bucket_seconds
        self.loop = loop
        self._batches = self._load_batches()
        self._iterator: Iterator[AcquisitionBatch] = itertools.cycle(self._batches) if loop else iter(self._batches)

    def _load_batches(self) -> list[AcquisitionBatch]:
        batch = cf_backend.read_file(self.path, bucket_seconds=self.bucket_seconds)
        chunk_sec = batch.metadata.get("bucket_seconds", self.default_exposure_sec)
        frames = int(max(1, round(batch.duration_sec / chunk_sec)))
        singles = batch.singles
        batches: list[AcquisitionBatch] = []
        for idx in range(frames):
            start_ps = idx * chunk_sec * 1e12
            end_ps = start_ps + chunk_sec * 1e12
            chunk = {
                ch: arr[(arr >= start_ps) & (arr < end_ps)].copy()
                for ch, arr in singles.items()
            }
            batches.append(
                AcquisitionBatch(
                    singles=chunk,
                    duration_sec=chunk_sec,
                    started_at=timing.utc_now(),
                    metadata={"source": str(self.path), "bucket_seconds": chunk_sec},
                )
            )
        return [b for b in batches if any(arr.size for arr in b.singles.values())]

    def capture(self, exposure_sec: float | None = None) -> AcquisitionBatch:
        try:
            return next(self._iterator)
        except StopIteration:
            raise RuntimeError("Replay finished and looping disabled.") from None
