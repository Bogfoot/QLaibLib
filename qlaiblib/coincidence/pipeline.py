"""Singles → coincidences orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

import numpy as np

from ..data.models import AcquisitionBatch, CoincidenceResult, CoincidenceSpec
from ..io import coincfinder_backend as cf_backend


@dataclass
class CoincidencePipeline:
    specs: Sequence[CoincidenceSpec]
    compute_accidentals: bool = True

    def run(self, batch: AcquisitionBatch) -> CoincidenceResult:
        counts: Dict[str, int] = {}
        accidentals: Dict[str, float] = {}
        for spec in self.specs:
            arrays = [batch.flatten(ch) for ch in spec.channels]
            if any(len(arr) == 0 for arr in arrays):
                counts[spec.label] = 0
                accidentals[spec.label] = 0.0
                continue
            if len(arrays) == 2:
                delay = spec.delay_ps or 0.0
                counts[spec.label] = cf_backend.count_pair(
                    arrays[0], arrays[1], window_ps=spec.window_ps, delay_ps=delay
                )
                if self.compute_accidentals:
                    accidentals[spec.label] = _estimate_accidentals_pair(
                        arrays[0], arrays[1], batch.duration_sec, spec.window_ps
                    )
            else:
                counts[spec.label] = cf_backend.count_nfold(
                    arrays, window_ps=spec.window_ps
                )
                accidentals[spec.label] = 0.0
        return CoincidenceResult(
            specs=self.specs,
            counts=counts,
            accidentals=accidentals,
            duration_sec=batch.duration_sec,
        )

    def labels(self) -> List[str]:
        return [spec.label for spec in self.specs]

    def update_delay(self, label: str, delay_ps: float) -> None:
        new_specs: List[CoincidenceSpec] = []
        for spec in self.specs:
            if spec.label == label:
                new_specs.append(
                    CoincidenceSpec(
                        label=spec.label,
                        channels=spec.channels,
                        window_ps=spec.window_ps,
                        delay_ps=delay_ps,
                    )
                )
            else:
                new_specs.append(spec)
        self.specs = tuple(new_specs)


def _estimate_accidentals_pair(a: np.ndarray, b: np.ndarray, duration: float, window_ps: float) -> float:
    if duration <= 0:
        return 0.0
    tau = window_ps * 1e-12
    return 2.0 * len(a) * len(b) * tau / duration
