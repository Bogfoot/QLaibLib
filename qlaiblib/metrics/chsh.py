"""CHSH S metric."""

from __future__ import annotations

from ..data.models import CoincidenceResult, MetricValue
from .core import REGISTRY


def _correlation(counts: dict[str, int], labels: tuple[str, str, str, str]) -> float:
    Npp = counts.get(labels[0], 0)
    Npm = counts.get(labels[1], 0)
    Nmp = counts.get(labels[2], 0)
    Nmm = counts.get(labels[3], 0)
    total = Npp + Npm + Nmp + Nmm
    if total == 0:
        return 0.0
    return (Npp + Nmm - Npm - Nmp) / total


def chsh_metric(result: CoincidenceResult) -> MetricValue:
    counts = result.counts
    E_ab = _correlation(counts, ("HH", "HV", "VH", "VV"))
    E_abp = _correlation(counts, ("HD", "HA", "VD", "VA"))
    E_apb = _correlation(counts, ("DH", "DV", "AH", "AV"))
    E_apbp = _correlation(counts, ("DD", "DA", "AD", "AA"))
    value = E_ab - E_abp + E_apb + E_apbp
    return MetricValue(
        name="CHSH_S",
        value=value,
        extras={
            "E_ab": E_ab,
            "E_abp": E_abp,
            "E_apb": E_apb,
            "E_apbp": E_apbp,
        },
    )


REGISTRY.register(chsh_metric)
