"""Launch the Tkinter dashboard with a real QuTAG backend."""

from qlaiblib import (
    QuTAGBackend,
    CoincidencePipeline,
    specs_from_delays,
    auto_calibrate_delays,
    LiveAcquisition,
    run_dashboard,
)

WINDOW_PS = 200.0
DELAY_SCAN = {
    "delay_start_ps": -8000.0,
    "delay_end_ps": 8000.0,
    "delay_step_ps": 50.0,
}


def main():
    backend = QuTAGBackend(exposure_sec=1.0)
    batch = backend.capture()
    delays = auto_calibrate_delays(batch, window_ps=WINDOW_PS, **DELAY_SCAN)
    specs = specs_from_delays(window_ps=WINDOW_PS, delays_ps=delays)
    pipeline = CoincidencePipeline(specs)
    controller = LiveAcquisition(backend, pipeline, exposure_sec=1.0)
    run_dashboard(controller)


if __name__ == "__main__":
    main()
