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
git clone https://github.com/Bogfoot/QLaibLib.git
cd QLaibLib
# pip install -e .
```

The CLI becomes available as `qlaib` and the package can be imported in Python.

### Installing coincfinder

The C++ coincidence engine lives in `coincfinder/`. To
use it on that platform, follow the next build instructions (it will be
found via `import coincfinder`), or copy it into your environment’s
`site-packages`.

To build the extension for coincfinder:

### Windows requirements

You require [CMake](https://cmake.org/download/).
You can use `x64 Native Tools Command Prompt for VS 20##`, or any other build tool you like.
You can download the `x64 Native Tools Command Prompt for Visual Studio 20##` by installing Visual Studio 20## from the official Microsoft website.
During installation, ensure you select the "Desktop development with C++" workload, which includes the necessary tools. After installation, you can find the command prompt in the Start menu under Visual Studio 20##.

### Linux requirements

Have CMake and build-essentials installed via:

```bash
sudo apt-get install cmake build-essentials
```

#### Building

```bash
cd coincfinder
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release
# The resulting coincfinder.*.so/.pyd will be under 
# build/ and it should also appear in the root.
```

After building, place the generated shared library on your `PYTHONPATH`
(it is automatically copied besides `qlaiblib/` or install it into `site-packages`). The
`qlaiblib.io.coincfinder_backend` module will import it at runtime.

## Hardware requirements

- QuTAG hardware with the `QuTAG_MC` Python bindings installed.
- The compiled `coincfinder` extension (already present in this folder). Place
  it on `PYTHONPATH` or keep it beside the package so it can be imported.
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

# Develop without hardware using the synthetic backend
qlaib live --mock --exposure 0.5
```

To script the same workflows, see:

	- `examples/process_bin_file.py` – load a recorded BIN file, auto-calibrate
	  delays, and print coincidences/metrics.
	- `examples/live_qutag.py` – initialize the QuTAG backend, calibrate once, and
	  launch the Tk dashboard with all live controls.
	- `examples/mock_quickstart.py` – Simulated plotter.

## Custom coincidence layouts

Coincidence logic is fully described by `CoincidenceSpec`, so you can define any
channel combinations (2-fold or higher) and plug them into the pipeline:

```python
from qlaiblib import CoincidencePipeline, CoincidenceSpec

specs = (
    CoincidenceSpec(label="AB", channels=(1, 3), window_ps=250.0, delay_ps=12.5),
    CoincidenceSpec(label="CD", channels=(2, 4), window_ps=250.0, delay_ps=-8.0),
    CoincidenceSpec(label="ABC", channels=(1, 3, 5), window_ps=300.0),
)
pipeline = CoincidencePipeline(specs)
```

- `window_ps` **and** `delay_ps` are specified in **picoseconds**.
- If you still want auto-delay calibration, pass your own `like_pairs` /
  `cross_pairs` into `specs_from_delays(window_ps=..., like_pairs=..., cross_pairs=...)`
  so the generated specs match your detector wiring.
- The CLI and Tk dashboard reflect whatever specs you supply, so custom labels
  automatically appear in plots, filters, and metrics.

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
