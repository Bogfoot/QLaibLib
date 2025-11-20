"""Plot singles + coincidences over time for a BIN file."""

from __future__ import annotations

import argparse
import dataclasses
import matplotlib.pyplot as plt
import numpy as np

from qlaiblib import CoincidencePipeline, DEFAULT_SPECS, auto_calibrate_delays
from qlaiblib.data.models import AcquisitionBatch
from qlaiblib.io import coincfinder_backend as cf_backend


def chunk_singles(batch: AcquisitionBatch, chunk_sec: float):
    edges = np.arange(0, batch.duration_sec + chunk_sec, chunk_sec)
    series = {"t": [], "singles": {}}
    channels = sorted(batch.singles.keys())
    for ch in channels:
        series["singles"][ch] = []
    for i in range(len(edges) - 1):
        start_ps = edges[i] * 1e12
        end_ps = edges[i + 1] * 1e12
        series["t"].append(edges[i + 1])
        for ch in channels:
            arr = batch.singles[ch]
            count = np.count_nonzero((arr >= start_ps) & (arr < end_ps))
            series["singles"][ch].append(count)
    return series


def chunk_coincidences(batch: AcquisitionBatch, chunk_sec: float, specs):
    edges = np.arange(0, batch.duration_sec + chunk_sec, chunk_sec)
    pipeline = CoincidencePipeline(specs)
    series = {"t": [], "coinc": {label: [] for label in pipeline.labels()}}
    for i in range(len(edges) - 1):
        start_ps = edges[i] * 1e12
        end_ps = edges[i + 1] * 1e12
        chunk = AcquisitionBatch(
            singles={ch: arr[(arr >= start_ps) & (arr < end_ps)] for ch, arr in batch.singles.items()},
            duration_sec=chunk_sec,
        )
        res = pipeline.run(chunk)
        series["t"].append(edges[i + 1])
        for label in pipeline.labels():
            series["coinc"][label].append(res.counts.get(label, 0))
    return series


def main():
    parser = argparse.ArgumentParser(description="Time-series plots for BIN file")
    parser.add_argument("path")
    parser.add_argument("--calib-seconds", type=float, default=1.0)
    parser.add_argument("--chunk", type=float, default=1)
    args = parser.parse_args()

    batch = cf_backend.read_file(args.path)
    calib_duration = min(batch.duration_sec, args.calib_seconds)
    calib_batch = AcquisitionBatch(
        singles={ch: arr[arr <= calib_duration * 1e12] for ch, arr in batch.singles.items()},
        duration_sec=calib_duration,
    )
    delays = auto_calibrate_delays(
        calib_batch,
        window_ps=250.0,
        delay_start_ps=8000,
        delay_end_ps=12000,
        delay_step_ps=10,
    )
    specs = tuple(
        dataclasses.replace(spec, delay_ps=delays.get(spec.label, spec.delay_ps or 0.0))
        for spec in DEFAULT_SPECS
    )

    single_ts = chunk_singles(batch, args.chunk)
    coinc_ts = chunk_coincidences(batch, args.chunk, specs)

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)
    for ch, values in single_ts["singles"].items():
        ax1.plot(single_ts["t"], values, label=f"Ch {ch}")
    ax1.set_ylabel("Singles per chunk")
    ax1.legend(ncol=4, fontsize=8)
    ax1.grid(True, alpha=0.2)

    for label, values in coinc_ts["coinc"].items():
        ax2.plot(coinc_ts["t"], values, label=label)
    ax2.set_xlabel("Time (s)")
    ax2.set_ylabel("Coincidences per chunk")
    ax2.legend(ncol=4, fontsize=8)
    ax2.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
