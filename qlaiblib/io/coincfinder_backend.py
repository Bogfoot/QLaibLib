"""Thin wrapper around the compiled coincfinder extension."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, Sequence, Tuple

import numpy as np

from ..data.models import AcquisitionBatch, CoincidenceSpec
from ..utils import timing

_COINCFINDER = None


def _module():
    global _COINCFINDER
    if _COINCFINDER is None:
        try:
            import coincfinder as _cf  # type: ignore
        except ImportError as exc:  # pragma: no cover - hardware dependency
            raise RuntimeError(
                "The coincfinder extension is required but is not importable."
            ) from exc
        _COINCFINDER = _cf
    return _COINCFINDER


@dataclass
class SinglesRaw:
    channel: int
    timestamps_ps: np.ndarray


def _flatten_single(raw_obj) -> np.ndarray:
    events = getattr(raw_obj, "events_per_second", None)
    if events is None:
        return np.asarray(raw_obj, dtype=np.int64)
    arrays = [np.asarray(bucket, dtype=np.int64) for bucket in events if bucket]
    if not arrays:
        return np.empty(0, dtype=np.int64)
    return np.concatenate(arrays)


def read_file(path: str | Path, *, bucket_seconds: float | None = None) -> AcquisitionBatch:
    module = _module()
    target_bucket = bucket_seconds if bucket_seconds and bucket_seconds > 0 else 1.0
    read_fn = getattr(module, "read_file_auto", None)
    if read_fn is None:
        raise RuntimeError("coincfinder module is missing read_file_auto")
    try:
        singles_map, duration_sec = read_fn(str(path), target_bucket)
    except TypeError:
        singles_map, duration_sec = read_fn(str(path))

    singles: Dict[int, np.ndarray] = {
        int(ch): _flatten_single(raw).astype(np.int64, copy=False)
        for ch, raw in singles_map.items()
    }
    return AcquisitionBatch(
        singles=singles,
        duration_sec=duration_sec,
        started_at=timing.utc_now(),
        metadata={"source": str(path), "bucket_seconds": target_bucket},
    )


def find_best_delay_ps(a: np.ndarray, b: np.ndarray, *, window_ps: float,
                       delay_start_ps: float, delay_end_ps: float,
                       delay_step_ps: float) -> float:
    module = _module()
    return float(
        module.find_best_delay_ps(
            a,
            b,
            coinc_window_ps=window_ps,
            delay_start_ps=delay_start_ps,
            delay_end_ps=delay_end_ps,
            delay_step_ps=delay_step_ps,
        )
    )


def count_pair(a: np.ndarray, b: np.ndarray, *, window_ps: float,
               delay_ps: float = 0.0) -> int:
    module = _module()
    return int(
        module.count_coincidences_with_delay_ps(a, b, window_ps, delay_ps)
    )


def count_nfold(arrays: Sequence[np.ndarray], *, window_ps: float) -> int:
    module = _module()
    return int(module.count_nfold_coincidences(arrays, window_ps))


def compute_histogram(
    a: np.ndarray,
    b: np.ndarray,
    *,
    window_ps: float,
    delay_start_ps: float,
    delay_end_ps: float,
    delay_step_ps: float,
) -> Tuple[np.ndarray, np.ndarray]:
    module = _module()
    histogram = module.compute_coincidences_for_range_ps(
        a,
        b,
        coinc_window_ps=window_ps,
        delay_start_ps=delay_start_ps,
        delay_end_ps=delay_end_ps,
        delay_step_ps=delay_step_ps,
    )
    offsets = np.arange(delay_start_ps, delay_end_ps + delay_step_ps, delay_step_ps)
    return offsets, np.asarray(histogram, dtype=np.int64)


class RollingSingles:
    """Expose coincfinder.RollingSingles with sane defaults."""

    def __init__(self, window_seconds: float):
        module = _module()
        self._impl = module.RollingSingles(window_seconds)

    def ingest(self, channel: int, timestamps_ps: Sequence[int]):
        self._impl.add(channel, timestamps_ps)

    def rate(self, channel: int) -> float:
        return float(self._impl.rate(channel))

    def coincidence_rate(self, channels: Sequence[int], window_ps: float) -> float:
        return float(self._impl.coincidence_rate(channels, window_ps))
