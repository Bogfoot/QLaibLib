"""Run the pipeline end-to-end without hardware."""

from qlaiblib import (
    MockBackend,
    CoincidencePipeline,
    CoincidenceSpec,
    LiveAcquisition,
    run_dashboard,
)

specs = (
    CoincidenceSpec(label="HH", channels=(1, 5), window_ps=200.0),
    CoincidenceSpec(label="VV", channels=(2, 6), window_ps=200.0),
    CoincidenceSpec(label="DD", channels=(3, 7), window_ps=200.0),
    CoincidenceSpec(label="AA", channels=(4, 8), window_ps=200.0),
)

backend = MockBackend(exposure_sec=0.5)
pipeline = CoincidencePipeline(specs)
controller = LiveAcquisition(backend, pipeline, exposure_sec=0.5)

if __name__ == "__main__":
    run_dashboard(controller)
