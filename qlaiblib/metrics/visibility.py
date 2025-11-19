"""Visibility style metrics."""

from __future__ import annotations

from ..data.models import CoincidenceResult, MetricValue
from .core import REGISTRY

_EPS = 1e-9


def _visibility(result: CoincidenceResult, like_labels, cross_labels, name: str) -> MetricValue:
    like = sum(result.counts.get(lbl, 0) for lbl in like_labels)
    cross = sum(result.counts.get(lbl, 0) for lbl in cross_labels)
    vis = (like - cross) / (like + cross + _EPS)
    return MetricValue(name=name, value=vis, extras={"like": like, "cross": cross})


def visibility_hv(result: CoincidenceResult) -> MetricValue:
    return _visibility(result, ("HH", "VV"), ("HV", "VH"), "visibility_HV")


def visibility_da(result: CoincidenceResult) -> MetricValue:
    return _visibility(result, ("DD", "AA"), ("DA", "AD"), "visibility_DA")


def visibility_avg(result: CoincidenceResult) -> MetricValue:
    hv = visibility_hv(result).value
    da = visibility_da(result).value
    vis = max(0.0, min(0.999, (hv + da) / 2.0))
    return MetricValue(name="visibility", value=vis, extras={"vis_HV": hv, "vis_DA": da})


REGISTRY.register(visibility_hv)
REGISTRY.register(visibility_da)
REGISTRY.register(visibility_avg)
