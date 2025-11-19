"""QBER style metrics."""

from __future__ import annotations

from ..data.models import CoincidenceResult, MetricValue
from .core import REGISTRY
from . import visibility


def _qber(value: float, name: str) -> MetricValue:
    return MetricValue(name=name, value=(1.0 - value) / 2.0)


def qber_hv(result: CoincidenceResult) -> MetricValue:
    return _qber(visibility.visibility_hv(result).value, "QBER_HV")


def qber_da(result: CoincidenceResult) -> MetricValue:
    return _qber(visibility.visibility_da(result).value, "QBER_DA")


def qber_total(result: CoincidenceResult) -> MetricValue:
    vis = visibility.visibility_avg(result).value
    return _qber(vis, "QBER_total")


REGISTRY.register(qber_hv)
REGISTRY.register(qber_da)
REGISTRY.register(qber_total)
