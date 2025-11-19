"""Metric infrastructure."""

from __future__ import annotations

from typing import Callable, Dict, Iterable, List

from ..data.models import CoincidenceResult, MetricValue

MetricFn = Callable[[CoincidenceResult], MetricValue]


class MetricRegistry:
    def __init__(self):
        self._metrics: Dict[str, MetricFn] = {}

    def register(self, metric_fn: MetricFn) -> None:
        self._metrics[metric_fn.__name__] = metric_fn

    def compute_all(self, result: CoincidenceResult) -> List[MetricValue]:
        values: List[MetricValue] = []
        for fn in self._metrics.values():
            values.append(fn(result))
        return values

    def names(self) -> List[str]:
        return list(self._metrics.keys())


REGISTRY = MetricRegistry()
