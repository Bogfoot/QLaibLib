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
  histograms, settings, and data/export tools. Auto-starts acquisition on launch
  (Start is disabled while running), keeps the coincidence window in sync
  between plots and histograms, shows per-pair contrast/heralding + accidentals
  in the legend, and exposes a status line (`Running | Exposure | Window`) so
  you can see edits take effect. Keyboard shortcuts (1–6) switch layouts;
  histogram auto-refresh and CSV/raw BIN export are built in.
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
# Exposure and coincidence-window edits in the UI apply live to acquisition + plots

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

## Configuring defaults & dashboard from code

All lab defaults live in `qlaiblib/coincidence/specs.py` and propagate to CLI, plotting, and the Tk dashboard:

- **DEFAULT_PAIRS / GHZ_TRIPLETS / DEFAULT_SPECS** – the canonical coincidence definitions. Edit these to change what gets captured and displayed.
- **SINGLES_PLOT_CHANNELS** – channels shown in singles time-series plots (keys 1/3/5 in the dashboard).
- **SINGLES_AS_RATE** – set to `True` to display singles as rates (counts/s) instead of raw counts.
- **COINCIDENCE_PLOT_LABELS** – controls which coincidence labels appear in plot modes 2/3/5 (coincidence traces).
- **CHSH_LABELS** – labels shown in CHSH view (mode 6).
- **DASHBOARD_TABS** – order/names of tabs in the live UI.

Delay auto-calibration defaults live in `qlaiblib/coincidence/delays.py`:

- **DEFAULT_REF_PAIRS / DEFAULT_CROSS_PAIRS** – channel pairs used to find per-channel delays.
- **auto_calibrate_delays(...)** + **specs_from_delays(...)** – utilities the CLI uses when you don’t pass `--use-default-specs`.

After changing defaults, reinstall locally so `qlaib` picks them up:

```bash
pip install --force-reinstall .
```

### CLI knobs for delays

- Use built-in defaults: `qlaib coincide --use-default-specs ...`
- Auto-calibrate with custom scan bounds (picoseconds):
  ```bash
  qlaib coincide --window-ps 200 --delay-start-ps -8000 --delay-end-ps 8000 --delay-step-ps 50
  ```
- Provide your own lab defaults: edit `DEFAULT_PAIRS` / `DEFAULT_CROSS_PAIRS` and `DEFAULT_SPECS` in `qlaiblib/coincidence/specs.py`, then reinstall (`pip install --force-reinstall .`). The CLI will pick them up automatically.

### How auto-calibrate (“autofinddelays”) works

- Source code: `qlaiblib/coincidence/delays.py` (`auto_calibrate_delays` + `specs_from_delays`).
- Inputs:
  - Pairs to scan: `DEFAULT_REF_PAIRS` (like-polarization) from the same file; editable for your wiring.
  - Scan parameters: `--window-ps`, `--delay-start-ps`, `--delay-end-ps`, `--delay-step-ps` CLI flags.
  - Data: the first acquisition batch from the backend (`backend.capture()`), flattened per channel.
- For each pair it sweeps delays, calls `coincfinder_backend.find_best_delay_ps` to maximize coincidences inside `window_ps`, and stores the best delay.
- `specs_from_delays` then assigns those delays to channels and builds the full `CoincidenceSpec` set (both like- and cross-pairs).

### Where `qlaib live` gets delays

- On start, `qlaib live` captures one exposure chunk from the backend, then calls `auto_calibrate_delays` with `DEFAULT_REF_PAIRS` and your CLI scan bounds to find per-channel delays.
- Those calibrated delays are passed to `specs_from_delays`, which builds the specs the dashboard uses for plots/metrics.
- Currently `live` always calibrates; if you want to skip calibration and force static lab defaults, set `DEFAULT_SPECS` (and delays) in `specs.py`, then change the CLI to use them or add a `--use-default-specs` flag similarly to `qlaib replay`.
- The live dashboard auto-starts acquisition. Exposure changes (CLI `--exposure` or the GUI field) and coincidence-window edits apply on the next chunk to both acquisition and plots. A status line shows the current mode/values, and the coincidence window stays in sync between time-series plots and the histogram tab.

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

## License
MIT — see `LICENSE` for details. Copyright (c) 2025 Adrian Udovičić, PhD student in physics at University of Ljubljana, Faculty of Mathematics and Physics.
