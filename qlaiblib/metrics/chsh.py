"""CHSH S metric."""

from __future__ import annotations

import builtins
import numpy as np
from uncertainties import ufloat

from ..data.models import CoincidenceResult, MetricValue
from .core import REGISTRY


def _correlation(counts: dict[str, int], labels: tuple[str, str, str, str]) -> tuple[float, float]:
    vals = [counts.get(lbl, 0) for lbl in labels]
    Npp, Npm, Nmp, Nmm = [
        ufloat(v, np.sqrt(builtins.max(v, 1.0))) for v in vals
    ]
    total = Npp + Npm + Nmp + Nmm
    if total.n <= 0:
        return 0.0, 0.0
    corr = (Npp + Nmm - Npm - Nmp) / total
    return corr.n, corr.s


def chsh_metric(result: CoincidenceResult) -> MetricValue:
    counts = result.counts
    E_ab, sig_ab = _correlation(counts, ("HH", "HV", "VH", "VV"))
    E_abp, sig_abp = _correlation(counts, ("HD", "HA", "VD", "VA"))
    E_apb, sig_apb = _correlation(counts, ("DH", "DV", "AH", "AV"))
    E_apbp, sig_apbp = _correlation(counts, ("DD", "DA", "AD", "AA"))
    value = E_ab - E_abp + E_apb + E_apbp
    sigma = np.sqrt(sig_ab**2 + sig_abp**2 + sig_apb**2 + sig_apbp**2)
    return MetricValue(
        name="CHSH_S",
        value=value,
        extras={
            "E_ab": E_ab,
            "E_abp": E_abp,
            "E_apb": E_apb,
            "E_apbp": E_apbp,
            "sigma": sigma,
        },
    )


REGISTRY.register(chsh_metric)
