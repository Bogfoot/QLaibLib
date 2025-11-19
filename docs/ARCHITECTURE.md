# QLaibLib Architecture

QLaibLib reorganizes the legacy scripts into a composable Python package focused on
photon-counting experiments with the QuTAG time-tagger and the custom `coincfinder`
engine.

## Package layout

```
qlaiblib/
├── __init__.py
├── acquisition/
│   ├── __init__.py
│   ├── base.py             # Abstract interfaces for time-tagger controllers
│   ├── qutag.py            # High-level QuTAG implementation using QuTAG_MC
│   └── mock.py             # Offline/simulated acquisition source for testing
├── coincidence/
│   ├── __init__.py
│   ├── delays.py           # Delay calibration helpers (auto-scan, caching)
│   └── pipeline.py         # Orchestrates singles → coincidences computations
├── data/
│   ├── __init__.py
│   └── models.py           # Dataclasses for singles, coincidences, metrics
├── io/
│   ├── __init__.py
│   └── coincfinder_backend.py   # Thin wrapper over the compiled coincfinder module
├── live/
│   ├── __init__.py
│   ├── controller.py       # Measurement loop with configurable exposure time
│   └── tk_dashboard.py     # Tkinter GUI that consumes the live controller
├── metrics/
│   ├── __init__.py
│   ├── core.py             # Metric base classes / registry
│   ├── qber.py             # QBER metrics (HV, DA, aggregate)
│   └── visibility.py       # Visibility/SNR style observables
├── plotting/
│   ├── __init__.py
│   └── static.py           # Matplotlib helpers for singles/coincidences
├── utils/
│   ├── __init__.py
│   └── timing.py           # Convenience wrappers for timestamps/durations
└── cli.py                  # Typer-based entry points (count, coincide, live)
```

## Design goals

1. **Hardware agnostic acquisition:** The `AcquisitionBackend` protocol defines
   the interaction with a time-tagger. The QuTAG backend wraps the provided
   `QuTAG_MC` library, while `MockBackend` can replay BIN/CSV files for tests.
2. **Deterministic coincidence pipeline:** `coincidence.pipeline` centralizes
   flattening, delay matching, and coincidence counting via `coincfinder`.
3. **Extensible metrics:** `metrics.core.Metric` exposes a common interface;
   QBER, visibility, and SNR plug into a registry to drive reports and live plots.
4. **Plot-first UX:** `plotting.static` gives thin wrappers returning Matplotlib
   axes so notebooks/scripts can compose figures without boilerplate; the Tkinter
   dashboard uses the same primitives for consistency.
5. **Live loop separation:** `live.controller.LiveAcquisition` handles the async
   measurement loop, while `live.tk_dashboard.DashboardApp` focuses purely on UI.
6. **Packaging:** `pyproject.toml` + CLI commands surface the functionality as
   `qlaib count`, `qlaib coincide`, `qlaib live`, etc., making it pip-installable.

This file should be kept up to date as the library evolves.
