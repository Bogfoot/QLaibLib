"""Data structures shared across QLaibLib."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Iterable, Mapping, MutableMapping, Sequence, Tuple

import numpy as np

SinglesMap = Dict[int, np.ndarray]


@dataclass
class AcquisitionBatch:
    """Container for a single acquisition chunk.

    Attributes
    ----------
    singles:
        Mapping of channel -> timestamps in picoseconds.
    duration_sec:
        Effective integration time returned by ``coincfinder``.
    started_at:
        Optional wall-clock timestamp (UTC) for the beginning of the chunk.
    metadata:
        Free-form dictionary for backend specific information.
    """

    singles: SinglesMap
    duration_sec: float
    started_at: datetime | None = None
    metadata: MutableMapping[str, object] = field(default_factory=dict)

    def total_events(self, channel: int | None = None) -> int:
        if channel is None:
            return sum(len(arr) for arr in self.singles.values())
        return len(self.singles.get(channel, ()))

    def flatten(self, channel: int) -> np.ndarray:
        return self.singles.get(channel, np.empty(0, dtype=np.int64))


@dataclass(frozen=True)
class CoincidenceSpec:
    """Describe an N-fold coincidence request."""

    label: str
    channels: Tuple[int, ...]
    window_ps: float
    delay_ps: float | None = None


@dataclass
class CoincidenceResult:
    """Counts returned from the coincidence pipeline."""

    specs: Sequence[CoincidenceSpec]
    counts: MutableMapping[str, int] = field(default_factory=dict)
    accidentals: MutableMapping[str, float] = field(default_factory=dict)
    duration_sec: float = 0.0

    def total(self) -> int:
        return sum(self.counts.values())


@dataclass
class MetricValue:
    """A computed metric with metadata for logging/plotting."""

    name: str
    value: float
    units: str | None = None
    extras: Mapping[str, float] | None = None
    timestamp: datetime | None = None


def merge_singles(chunks: Iterable[AcquisitionBatch]) -> AcquisitionBatch:
    """Concatenate multiple batches into one virtual batch."""

    singles: Dict[int, np.ndarray] = {}
    duration = 0.0
    started_at = None
    for chunk in chunks:
        duration += chunk.duration_sec
        if started_at is None:
            started_at = chunk.started_at
        for ch, arr in chunk.singles.items():
            if ch not in singles:
                singles[ch] = arr.copy()
            else:
                singles[ch] = np.concatenate((singles[ch], arr))
    return AcquisitionBatch(singles=singles, duration_sec=duration, started_at=started_at)
