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
- **Metrics**: built-in visibility (HV, DA, total) and QBER metrics plugged into
  a registry so new observables can be added declaratively.
- **Plotting**: Matplotlib helpers for singles, coincidences, and metric
  summaries; reusable both in scripts and in the dashboard.
- **Live dashboard**: Tkinter GUI with configurable exposure time that streams
  singles, coincidences, and metrics in real time. Includes a settings tab to
  toggle channels/pairs, manually override delays, and compute per-pair
  histograms without leaving the app.
- **CLI**: `qlaib` entry point with `count`, `coincide`, and `live` commands.

## Installation

Clone the repository and install in editable mode:

```bash
pip install -e .
```

The CLI becomes available as `qlaib` and the package can be imported in Python.

### Installing coincfinder

The C++ coincidence engine lives in `coincfinder/` and a pre-built binary
(`coincfinder.cp312-win_amd64.pyd`) is included for Windows + Python 3.12. To
use it on that platform, simply keep the `.pyd` next to the project (it will be
found via `import coincfinder`), or copy it into your virtual environment’s
`site-packages`.

To build the extension for other platforms or Python versions:

```bash
cd coincfinder
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
# The resulting coincfinder.*.so/.pyd will be under build/ and it should also appear in the root.
```

After building, place the generated shared library on your `PYTHONPATH`
(e.g., drop it beside `qlaiblib/` or install it into `site-packages`). The
`qlaiblib.io.coincfinder_backend` module will import it at runtime.

## Hardware requirements

- QuTAG hardware with the `QuTAG_MC` Python bindings installed.
- The compiled `coincfinder` extension (already present in this folder). Place
  it on `PYTHONPATH` or keep it beside the package so it can be imported.
- For live plotting, Tkinter must be available (ships with standard Python on
  Windows/macOS/Linux).

## CLI usage

```bash
# Count singles for one exposure chunk and plot the bar chart
qlaib count --exposure 1.5 --plot

# Capture coincidences after automatically calibrating delays
qlaib coincide --exposure 0.5 --window-ps 200

# Launch the Tkinter dashboard with 2-second integration
qlaib live --exposure 2.0

# Process an existing BIN file (≈5 s capture) without hardware
qlaib replay Data/sample_capture.bin --window-ps 200 --plot

# Develop without hardware using the synthetic backend
qlaib live --mock --exposure 0.5
```

To script the same workflows, see:

- `examples/process_bin_file.py` – load a recorded BIN file, auto-calibrate
  delays, and print coincidences/metrics.
- `examples/live_qutag.py` – initialize the QuTAG backend, calibrate once, and
  launch the Tk dashboard with all live controls.

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
through the packaged interfaces above.
