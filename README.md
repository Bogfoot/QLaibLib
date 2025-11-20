# QLaibLib
## Quantum Laibach Library

A reorganized Python package that wraps the existing QuTAG 
toolchain. QLaibLib exposes a clean API, plotting helpers, metrics
(QBER, visibility, contrast), and a Tkinter-based live dashboard without needing
a browser. Ready and lab friendly. :)

## Features

- **Singles acquisition**: capture singles per channel via the QuTAG hardware or
  the mock backend for offline development.
- **Coincidence pipeline**: calibrate per-pair delays, compute 2-fold or N-fold
  coincidence rates, and estimate accidentals.
- **Metrics**: built-in visibility (HV, DA, total), QBER, and CHSH S metrics
  plugged into a registry so new observables can be added declaratively.
- **Plotting**: Matplotlib helpers for singles, coincidences, and metric
  summaries; reusable both in scripts and in the dashboard.
- **Live dashboard**: Tkinter GUI with tabs for live time-series plots, delay
  histograms, settings, and data/export tools. Supports keyboard shortcuts (1–6)
  to switch plot layouts (including a CHSH view with all 16 coincidence pairs
  and S±σ), per-pair contrast/heralding stats, histogram auto-refresh, and a
  history buffer (default 500 points) with CSV/raw BIN export buttons.
- **CLI**: `qlaib` entry point with `count`, `coincide`, and `live` commands.

## Installation

Clone the repository and install (the build now auto-compiles the C++
`coincfinder` module via [scikit-build-core](https://github.com/scikit-build/scikit-build-core)):

```bash
git clone https://github.com/Bogfoot/QLaibLib.git
cd QLaibLib
python -m venv .venv && source .venv/bin/activate  # optional but recommended
pip install .
```

Installation requirements:

- Python ≥ 3.10
- `cmake>=3.18` and `ninja` (installed automatically by pip if missing, or install
  system packages such as `sudo apt install cmake ninja-build` / Homebrew)
- A C++20 compiler (Visual Studio Build Tools on Windows, `build-essential`/`clang`
  on Linux/macOS)

Once published to PyPI you can simply run `pip install qlaiblib` on any machine
with those prerequisites. For developer builds, `python -m build` produces wheels
in `dist/` that already include the compiled `coincfinder` extension.

## Hardware requirements

- QuTAG hardware with the `QuTAG_MC` Python bindings installed.
- The C++ `coincfinder` extension (built automatically during `pip install` or
  bundled in prebuilt wheels once published).
- For live plotting, Tkinter must be available (ships with standard Python on
  Windows/macOS/Linux).

## CLI usage
### Experimental

```bash
# Count singles for one exposure chunk and plot the bar chart
qlaib count --exposure 1.5 --plot

# Capture coincidences after automatically calibrating delays
qlaib coincide --exposure 0.5 --window-ps 200

# Launch the Tkinter dashboard with 2-second integration
qlaib live --exposure 2.0

# Process an existing BIN file (≈5 s capture) without hardware
qlaib replay Data/sample_capture.bin --window-ps 200 --plot

# Plot singles/coincidences + metric time series from a BIN file (default 1 s chunks)
qlaib replay Data/sample_capture.bin --plot --timeseries

# Skip auto-delay calibration and use DEFAULT_SPECS (lab defaults)
qlaib replay Data/sample_capture.bin --use-default-specs --plot

# Ingest BIN file using the actual exposure time per bucket (e.g., 0.4 s)
qlaib replay Data/sample_capture.bin --bucket-seconds 0.4 --plot --timeseries

# Run the live dashboard in demo mode, replaying a BIN capture instead of hardware
# (press keys 1–6 to switch between singles/coincidences/metrics/CHSH views)
qlaib live --demo-file Data/sample_capture.bin --bucket-seconds 0.4 --history-points 800

# Develop without hardware using the synthetic backend
qlaib live --mock --exposure 0.5
```

To script the same workflows, see:

	- `examples/process_bin_file.py` – load a recorded BIN file, auto-calibrate
	  delays, and print coincidences/metrics.
- `examples/live_qutag.py` – initialize the QuTAG backend, calibrate once, and
  launch the Tk dashboard with all live controls.
- `examples/mock_quickstart.py` – Simulated plotter.
- `examples/bin_custom_specs.py` – calibrate using the first N seconds of a BIN
  file, apply custom coincidence specs (including N-fold), and plot coincidences +
  metrics such as visibility/QBER.
- `examples/bin_default_timeseries.py` – use `DEFAULT_SPECS`, auto-calibrate on
  the first N seconds of a BIN file, and visualize both aggregate metrics and
  per-chunk time series.
- `examples/bin_timeseries_only.py` – plot singles and coincidences as time series
  without extra metrics (useful for quick sanity checks).

## Custom coincidence layouts

Coincidence logic is fully described by `CoincidenceSpec`, so you can define any
channel combinations (2-fold or higher) and plug them into the pipeline:

```python
from qlaiblib import CoincidencePipeline, CoincidenceSpec, DEFAULT_SPECS

specs = DEFAULT_SPECS  # ready-to-use H/V/D/A pairs + GHZ-style triplets
pipeline = CoincidencePipeline(specs)

# or build your own specs ad-hoc
custom_specs = (
    CoincidenceSpec(label="AB", channels=(1, 3), window_ps=250.0, delay_ps=12.5),
    CoincidenceSpec(label="CD", channels=(2, 4), window_ps=250.0, delay_ps=-8.0),
    CoincidenceSpec(label="ABC", channels=(1, 3, 5), window_ps=300.0),
)
custom_pipeline = CoincidencePipeline(custom_specs)
```

- `window_ps` **and** `delay_ps` are specified in **picoseconds**.
- If you still want auto-delay calibration, pass your own `like_pairs` /
  `cross_pairs` into `specs_from_delays(window_ps=..., like_pairs=..., cross_pairs=...)`
  so the generated specs match your detector wiring.
- The CLI and Tk dashboard reflect whatever specs you supply, so custom labels
  automatically appear in plots, filters, and metrics.

- **New installs/lab defaults**: set `DEFAULT_SPECS` in code and wire it directly
  into `CoincidencePipeline` so everyone sees the same definitions.

### Using specs across the APIs

- **CLI**: tweak `qlaiblib/cli.py` where `CoincidencePipeline(specs)` is created
  (e.g., replace `specs = specs_from_delays(...)` with `specs = DEFAULT_SPECS`)
  to hard-code lab defaults when you don’t need auto-delay scans.
- **Live dashboard**:
  ```python
  from qlaiblib import LiveAcquisition, MockBackend, CoincidencePipeline, DEFAULT_SPECS, run_dashboard
  backend = MockBackend(exposure_sec=1.0)
  pipeline = CoincidencePipeline(DEFAULT_SPECS)
  controller = LiveAcquisition(backend, pipeline)
  run_dashboard(controller)
  ```
- **Offline scripts** (BIN replay, notebooks): pass `DEFAULT_SPECS` into the
  pipeline exactly as shown above, or mix in your own N-fold coincidences.

## Python API glimpse

```python
from qlaiblib import (
    QuTAGBackend,
    CoincidencePipeline,
    auto_calibrate_delays,
    specs_from_delays,
    LiveAcquisition,
    run_dashboard,
)

backend = QuTAGBackend(exposure_sec=1.0)
batch = backend.capture()
cal_delays = auto_calibrate_delays(batch, window_ps=200, delay_start_ps=-8000,
                                  delay_end_ps=8000, delay_step_ps=50)
specs = specs_from_delays(window_ps=200, delays_ps=cal_delays)
pipeline = CoincidencePipeline(specs)
controller = LiveAcquisition(backend, pipeline)
run_dashboard(controller)
```

## Legacy scripts

The original helper scripts remain untouched for reference (`Print_Counts_and_Stats.py`,
`Stability_Check_and_Record.py`, etc.), but new development should happen
through the packaged interfaces above. They can be distributed upon reasonable request.
