"""Default coincidence spec helpers and dashboard layout presets."""

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

# Singles channels to plot in time-series views (keys 1/3/5).
SINGLES_PLOT_CHANNELS = tuple(range(1, 9))

# If True, dashboard singles plots show rates (counts per second) instead of raw counts.
SINGLES_AS_RATE = True

# Which coincidence labels should appear in the live "coincidences" plots (keys 2,3,5).
# By default we show all specs, but you can shorten or reorder this tuple.
COINCIDENCE_PLOT_LABELS = tuple(spec.label for spec in DEFAULT_SPECS if len(spec.channels) >= 2)

# Order of CHSH coincidence pairs for the CHSH view (key 6).
CHSH_LABELS = (
    "HH", "HV", "VH", "VV",
    "HD", "HA", "VD", "VA",
    "DH", "DV", "AH", "AV",
    "DD", "DA", "AD", "AA",
)

# Dashboard tab order and labels. Modify this tuple to reconfigure the live UI.
# Format: (key, label) where `key` matches the builder name in the Tk dashboard.
DASHBOARD_TABS = (
    ("plots", "Plots"),
    ("histograms", "Histograms"),
    ("settings", "Settings"),
    ("export", "Data / Export"),
)

__all__ = [
    "DEFAULT_PAIRS",
    "GHZ_TRIPLETS",
    "DEFAULT_SPECS",
    "SINGLES_PLOT_CHANNELS",
    "SINGLES_AS_RATE",
    "COINCIDENCE_PLOT_LABELS",
    "CHSH_LABELS",
    "DASHBOARD_TABS",
]
