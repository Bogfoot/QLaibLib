"""Process a recorded BIN file (~5 s capture) and print coincidences/metrics."""

import argparse

from qlaiblib import CoincidencePipeline, specs_from_delays, auto_calibrate_delays
from qlaiblib.io import coincfinder_backend as cf_backend
from qlaiblib.metrics import REGISTRY


def main():
    parser = argparse.ArgumentParser(description="Process QuTAG BIN file with QLaibLib")
    parser.add_argument("path", help="Path to BIN file produced by writeTimestamps")
    parser.add_argument("--window", type=float, default=200.0, help="Coincidence window in ps")
    parser.add_argument("--delay-start", type=float, default=-8000.0)
    parser.add_argument("--delay-end", type=float, default=8000.0)
    parser.add_argument("--delay-step", type=float, default=50.0)
    args = parser.parse_args()

    batch = cf_backend.read_file(args.path)
    delays = auto_calibrate_delays(
        batch,
        window_ps=args.window,
        delay_start_ps=args.delay_start,
        delay_end_ps=args.delay_end,
        delay_step_ps=args.delay_step,
    )
    specs = specs_from_delays(window_ps=args.window, delays_ps=delays)
    pipeline = CoincidencePipeline(specs)
    coincidences = pipeline.run(batch)
    metrics = REGISTRY.compute_all(coincidences)

    print(f"Loaded {args.path} (duration {batch.duration_sec:.2f} s)")
    print("Label\tCounts\tAccidentals")
    for label in pipeline.labels():
        print(
            f"{label}\t{coincidences.counts.get(label, 0)}\t{coincidences.accidentals.get(label, 0):.2f}"
        )
    print("--- Metrics ---")
    for metric in metrics:
        print(f"{metric.name}: {metric.value:.4f}")


if __name__ == "__main__":
    main()
