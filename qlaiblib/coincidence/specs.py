"""Default coincidence spec helpers."""

from __future__ import annotations

from ..data.models import CoincidenceSpec

# Basic 2-fold pairs for the standard 1↔5, 2↔6, etc. mapping
DEFAULT_PAIRS = (
    CoincidenceSpec(label="HH", channels=(1, 5), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="VV", channels=(2, 6), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="DD", channels=(3, 7), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="AA", channels=(4, 8), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="HV", channels=(1, 6), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="VH", channels=(2, 5), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="DA", channels=(3, 8), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="AD", channels=(4, 7), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="HD", channels=(1, 7), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="HA", channels=(1, 8), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="VD", channels=(2, 7), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="VA", channels=(2, 8), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="DH", channels=(3, 5), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="DV", channels=(3, 6), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="AH", channels=(4, 5), window_ps=200.0, delay_ps=0.0),
    CoincidenceSpec(label="AV", channels=(4, 6), window_ps=200.0, delay_ps=0.0),
)

# Example N-fold (GHZ-style) coincidences built from three channels
GHZ_TRIPLETS = (
    CoincidenceSpec(label="GHZ_135", channels=(1, 3, 5), window_ps=300.0),
    CoincidenceSpec(label="GHZ_246", channels=(2, 4, 6), window_ps=300.0),
)

# Convenience tuple that can be imported directly in scripts / live dashboards
DEFAULT_SPECS = DEFAULT_PAIRS + GHZ_TRIPLETS

__all__ = ["DEFAULT_PAIRS", "GHZ_TRIPLETS", "DEFAULT_SPECS"]
