"""Delay calibration utilities."""

from __future__ import annotations

from typing import Dict, Iterable, Sequence, Tuple

from ..data.models import AcquisitionBatch, CoincidenceSpec
from ..io import coincfinder_backend as cf_backend

DEFAULT_REF_PAIRS: Tuple[Tuple[str, int, int], ...] = (
    ("HH", 1, 5),
    ("VV", 2, 6),
    ("DD", 3, 7),
    ("AA", 4, 8),
)

DEFAULT_CROSS_PAIRS: Tuple[Tuple[str, int, int], ...] = (
    ("HV", 1, 6),
    ("VH", 2, 5),
    ("DA", 3, 8),
    ("AD", 4, 7),
    ("HD", 1, 7),
    ("HA", 1, 8),
    ("VD", 2, 7),
    ("VA", 2, 8),
    ("DH", 3, 5),
    ("DV", 3, 6),
    ("AH", 4, 5),
    ("AV", 4, 6),
)


def auto_calibrate_delays(
    batch: AcquisitionBatch,
    pairs: Sequence[Tuple[str, int, int]] = DEFAULT_REF_PAIRS,
    *,
    window_ps: float,
    delay_start_ps: float,
    delay_end_ps: float,
    delay_step_ps: float,
) -> Dict[str, float]:
    delays: Dict[str, float] = {}
    for label, ch_a, ch_b in pairs:
        arr_a = batch.flatten(ch_a)
        arr_b = batch.flatten(ch_b)
        if len(arr_a) == 0 or len(arr_b) == 0:
            delays[label] = 0.0
            continue
        delays[label] = cf_backend.find_best_delay_ps(
            arr_a,
            arr_b,
            window_ps=window_ps,
            delay_start_ps=delay_start_ps,
            delay_end_ps=delay_end_ps,
            delay_step_ps=delay_step_ps,
        )
    return delays


def specs_from_delays(
    *,
    window_ps: float,
    like_pairs: Sequence[Tuple[str, int, int]] = DEFAULT_REF_PAIRS,
    cross_pairs: Sequence[Tuple[str, int, int]] = DEFAULT_CROSS_PAIRS,
    delays_ps: Dict[str, float],
) -> Tuple[CoincidenceSpec, ...]:
    specs = []
    channel_delay: Dict[int, float] = {}
    for label, ch_a, ch_b in like_pairs:
        delay = delays_ps.get(label, 0.0)
        channel_delay[ch_a] = delay
        channel_delay[ch_b] = delay
        specs.append(
            CoincidenceSpec(
                label=label,
                channels=(ch_a, ch_b),
                window_ps=window_ps,
                delay_ps=delay,
            )
        )
    for label, ch_a, ch_b in cross_pairs:
        delay = channel_delay.get(ch_a, channel_delay.get(ch_b, 0.0))
        specs.append(
            CoincidenceSpec(
                label=label,
                channels=(ch_a, ch_b),
                window_ps=window_ps,
                delay_ps=delay,
            )
        )
    return tuple(specs)
