"""Rolling history buffer for live plots."""

from __future__ import annotations

from collections import deque
from typing import Deque, Dict, List

import numpy as np

from ..data.models import CoincidenceResult, MetricValue


class HistoryBuffer:
    def __init__(self, max_points: int = 500):
        self.max_points = max_points
        self.times: Deque[float] = deque(maxlen=max_points)
        self.singles: Dict[int, Deque[float]] = {}
        self.coincidences: Dict[str, Deque[float]] = {}
        self.metrics: Dict[str, Deque[float]] = {}
        self.metric_sigmas: Dict[str, Deque[float]] = {}

    def resize(self, max_points: int):
        if max_points == self.max_points:
            return
        self.max_points = max_points
        self.times = deque(self.times, maxlen=max_points)
        for key in list(self.singles.keys()):
            self.singles[key] = deque(self.singles[key], maxlen=max_points)
        for key in list(self.coincidences.keys()):
            self.coincidences[key] = deque(self.coincidences[key], maxlen=max_points)
        for key in list(self.metrics.keys()):
            self.metrics[key] = deque(self.metrics[key], maxlen=max_points)
        for key in list(self.metric_sigmas.keys()):
            self.metric_sigmas[key] = deque(self.metric_sigmas[key], maxlen=max_points)

    def append(
        self,
        timestamp: float,
        singles_counts: Dict[int, float],
        coincidences: CoincidenceResult,
        metrics: List[MetricValue],
    ) -> None:
        self.times.append(timestamp)
        for ch, value in singles_counts.items():
            self.singles.setdefault(ch, deque(maxlen=self.max_points)).append(value)
        for label in coincidences.counts:
            self.coincidences.setdefault(label, deque(maxlen=self.max_points)).append(
                coincidences.counts[label]
            )
        for metric in metrics:
            self.metrics.setdefault(metric.name, deque(maxlen=self.max_points)).append(metric.value)
            sigma = metric.extras.get("sigma") if metric.extras else None
            if sigma is not None:
                self.metric_sigmas.setdefault(metric.name, deque(maxlen=self.max_points)).append(float(sigma))

    def as_arrays(self) -> Dict[str, np.ndarray]:
        return {name: np.asarray(values) for name, values in self.metrics.items()}
