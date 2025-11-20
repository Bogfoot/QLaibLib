"""Process a BIN file with custom coincidence specs and calibration window."""

from __future__ import annotations

import argparse
import matplotlib.pyplot as plt

from qlaiblib import CoincidencePipeline, CoincidenceSpec, auto_calibrate_delays
from qlaiblib.data.models import AcquisitionBatch
from qlaiblib.io import coincfinder_backend as cf_backend
from qlaiblib.metrics import REGISTRY
from qlaiblib.plotting import static as static_plots


CUSTOM_PAIRS = (
    ("HV_like", 1, 5),
    ("HV_cross", 1, 6),
    ("DA_like", 3, 7),
    ("DA_cross", 3, 8),
)

GHZ_NFOLD = (
    CoincidenceSpec(label="ABC", channels=(1, 3, 5), window_ps=300.0),
    CoincidenceSpec(label="DEF", channels=(2, 4, 6), window_ps=300.0),
)


def clamp_batch(batch: AcquisitionBatch, window_sec: float) -> AcquisitionBatch:
    if window_sec <= 0:
        return batch
    limit_ps = window_sec * 1e12
    singles = {ch: arr[arr <= limit_ps] for ch, arr in batch.singles.items()}
    duration = min(batch.duration_sec, window_sec)
    return AcquisitionBatch(singles=singles, duration_sec=duration, started_at=batch.started_at)


def build_specs(delays):
    specs = []
    for label, ch_a, ch_b in CUSTOM_PAIRS:
        specs.append(
            CoincidenceSpec(
                label=label,
                channels=(ch_a, ch_b),
                window_ps=250.0,
                delay_ps=delays.get(label, 0.0),
            )
        )
    specs.extend(GHZ_NFOLD)
    return tuple(specs)


def main():
    parser = argparse.ArgumentParser(description="Process BIN file with custom specs")
    parser.add_argument("path", help="Path to BIN file (~5 s capture)")
    parser.add_argument("--calib-seconds", type=float, default=2.0,
                        help="Seconds from file used for delay calibration")
    args = parser.parse_args()

    batch = cf_backend.read_file(args.path)
    calib_batch = clamp_batch(batch, args.calib_seconds)

    delays = auto_calibrate_delays(
        calib_batch,
        pairs=[(label, ch_a, ch_b) for label, ch_a, ch_b in CUSTOM_PAIRS],
        window_ps=200.0,
        delay_start_ps=-8000.0,
        delay_end_ps=8000.0,
        delay_step_ps=50.0,
    )

    specs = build_specs(delays)
    pipeline = CoincidencePipeline(specs)
    result = pipeline.run(batch)
    metrics = REGISTRY.compute_all(result)

    print(f"Processed {args.path} (duration {batch.duration_sec:.2f} s)")
    for label in pipeline.labels():
        print(f"{label}: {result.counts.get(label, 0)} coincidences")
    for metric in metrics:
        print(f"{metric.name}: {metric.value:.4f}")

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4))
    static_plots.plot_coincidences(result, ax=ax1)
    static_plots.plot_metrics(metrics, ax=ax2)
    fig.suptitle("Custom coincidence analysis")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
