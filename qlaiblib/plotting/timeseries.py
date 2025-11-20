"""Time-series chunking helpers for singles/coincidences."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Sequence, Iterable, Tuple

import matplotlib.pyplot as plt
import numpy as np

from ..coincidence.pipeline import CoincidencePipeline
from ..data.models import AcquisitionBatch, CoincidenceSpec
from ..metrics import REGISTRY


@dataclass
class TimeSeriesResult:
    times: np.ndarray
    singles: Dict[int, np.ndarray]
    coincidences: Dict[str, np.ndarray]
    metrics: Dict[str, np.ndarray]


def chunk_singles(batch: AcquisitionBatch, chunk_sec: float) -> Dict[int, np.ndarray]:
    edges = np.arange(0, batch.duration_sec + chunk_sec, chunk_sec)
    channel_counts: Dict[int, list[int]] = {ch: [] for ch in batch.singles.keys()}
    for start, end in zip(edges[:-1], edges[1:]):
        start_ps, end_ps = start * 1e12, end * 1e12
        for ch, arr in batch.singles.items():
            count = np.count_nonzero((arr >= start_ps) & (arr < end_ps))
            channel_counts[ch].append(int(count))
    return {ch: np.asarray(counts) for ch, counts in channel_counts.items()}


def compute_timeseries(
    batch: AcquisitionBatch,
    chunk_sec: float | None,
    specs: Sequence[CoincidenceSpec],
) -> TimeSeriesResult:
    if not chunk_sec or chunk_sec <= 0:
        bucket_hint = None
        if batch.metadata:
            bucket_hint = batch.metadata.get("bucket_seconds") or batch.metadata.get("exposure_sec")
        chunk_sec = float(bucket_hint) if bucket_hint and bucket_hint > 0 else 1.0
    edges = np.arange(0, batch.duration_sec + chunk_sec, chunk_sec)
    pipeline = CoincidencePipeline(specs)
    singles = chunk_singles(batch, chunk_sec)
    coinc_counts: Dict[str, list[int]] = {label: [] for label in pipeline.labels()}
    metric_series: Dict[str, list[float]] = {}
    times: list[float] = []
    for start, end in zip(edges[:-1], edges[1:]):
        start_ps, end_ps = start * 1e12, end * 1e12
        chunk = AcquisitionBatch(
            singles={ch: arr[(arr >= start_ps) & (arr < end_ps)] for ch, arr in batch.singles.items()},
            duration_sec=min(chunk_sec, batch.duration_sec - start),
        )
        result = pipeline.run(chunk)
        times.append(end)
        for label in pipeline.labels():
            coinc_counts[label].append(result.counts.get(label, 0))
        for metric in REGISTRY.compute_all(result):
            metric_series.setdefault(metric.name, []).append(metric.value)
    coincidences = {label: np.asarray(values) for label, values in coinc_counts.items()}
    metrics = {name: np.asarray(values) for name, values in metric_series.items()}
    return TimeSeriesResult(times=np.asarray(times), singles=singles, coincidences=coincidences, metrics=metrics)


def plot_timeseries(
    ts: TimeSeriesResult,
    *,
    singles_ax=None,
    coincid_ax=None,
    metric_axes: Sequence = (),
    metric_groups: Sequence[Tuple[str, Iterable[str]]] | None = None,
):
    singles_ax = singles_ax or plt.gca()
    for ch, values in ts.singles.items():
        singles_ax.plot(ts.times[: len(values)], values, label=f"Ch {ch}")
    singles_ax.set_ylabel("Singles / chunk")
    singles_ax.legend(ncol=4, fontsize=8)
    singles_ax.grid(True, alpha=0.2)

    if coincid_ax is not None:
        for label, values in ts.coincidences.items():
            coincid_ax.plot(ts.times[: len(values)], values, label=label)
        coincid_ax.set_ylabel("Coincidences / chunk")
        coincid_ax.legend(ncol=4, fontsize=8)
        coincid_ax.grid(True, alpha=0.2)

    if metric_axes:
        for ax in metric_axes:
            ax.set_visible(False)
    if metric_groups and metric_axes:
        for ax, (group_name, names) in zip(metric_axes, metric_groups):
            ax.set_visible(True)
            for name in names:
                values = ts.metrics.get(name)
                if values is None:
                    continue
                ax.plot(ts.times[: len(values)], values, label=name)
            ax.set_ylabel(group_name)
            ax.legend(ncol=2, fontsize=8)
            ax.grid(True, alpha=0.2)
