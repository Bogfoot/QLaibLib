"""Process a BIN file with default specs, calibrate, and plot time series."""

from __future__ import annotations

import argparse
from pathlib import Path

import dataclasses

import matplotlib.pyplot as plt
import numpy as np

from qlaiblib import CoincidencePipeline, DEFAULT_SPECS, auto_calibrate_delays
from qlaiblib.coincidence.specs import DEFAULT_PAIRS
from qlaiblib.io import coincfinder_backend as cf_backend
from qlaiblib.metrics import REGISTRY
from qlaiblib.plotting import static as static_plots


def chunk_batch(batch, chunk_sec, specs):
    singles = batch.singles
    duration = batch.duration_sec
    edges = np.arange(0, duration + chunk_sec, chunk_sec)
    timeseries = {spec.label: [] for spec in DEFAULT_PAIRS}
    timeseries["t"] = []
    pipeline = CoincidencePipeline(specs)
    for i in range(len(edges) - 1):
        start_ps = edges[i] * 1e12
        end_ps = edges[i + 1] * 1e12
        chunk_singles = {
            ch: arr[(arr >= start_ps) & (arr < end_ps)]
            for ch, arr in singles.items()
        }
        from qlaiblib.data.models import AcquisitionBatch

        chunk = AcquisitionBatch(singles=chunk_singles, duration_sec=chunk_sec)
        res = pipeline.run(chunk)
        timeseries["t"].append(edges[i + 1])
        for label in pipeline.labels():
            timeseries[label].append(res.counts.get(label, 0))
    return timeseries


def main():
    parser = argparse.ArgumentParser(description="BIN analysis with default specs")
    parser.add_argument("path")
    parser.add_argument("--calib-seconds", type=float, default=2.0)
    parser.add_argument("--timeseries-chunk", type=float, default=0.5)
    args = parser.parse_args()

    batch = cf_backend.read_file(args.path)
    calib_duration = min(batch.duration_sec, args.calib_seconds)
    from qlaiblib.data.models import AcquisitionBatch

    calib_batch = AcquisitionBatch(
        singles={ch: arr[arr <= calib_duration * 1e12] for ch, arr in batch.singles.items()},
        duration_sec=calib_duration,
    )
    delays = auto_calibrate_delays(
        calib_batch,
        window_ps=250.0,
        delay_start_ps=-8000,
        delay_end_ps=80000,
        delay_step_ps=10,
    )
    specs = tuple(
        dataclasses.replace(spec, delay_ps=delays.get(spec.label, spec.delay_ps or 0.0))
        for spec in DEFAULT_PAIRS
    )
    pipeline = CoincidencePipeline(specs)
    result = pipeline.run(batch)
    metrics = REGISTRY.compute_all(result)

    print(f"Processed {Path(args.path).name} with duration {batch.duration_sec:.2f}s")
    for label in pipeline.labels():
        print(f"{label}: {result.counts.get(label, 0)}")
    for metric in metrics:
        print(f"{metric.name}: {metric.value:.4f}")

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    static_plots.plot_coincidences(result, ax=axes[0, 0])
    static_plots.plot_metrics(metrics, ax=axes[0, 1])

    ts = chunk_batch(batch, args.timeseries_chunk, specs)
    ax = axes[1, 0]
    for label in pipeline.labels():
        ax.plot(ts["t"], ts[label], label=label)
    ax.set_title("Coincidences per chunk")
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Counts")
    ax.legend(fontsize=8, ncol=2)

    axes[1, 1].axis("off")
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
