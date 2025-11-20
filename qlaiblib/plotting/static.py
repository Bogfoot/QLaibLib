"""Convenience Matplotlib plots."""

from __future__ import annotations

from typing import Iterable, Sequence

import matplotlib.pyplot as plt

from ..data.models import AcquisitionBatch, CoincidenceResult, MetricValue


def plot_singles(
    batch: AcquisitionBatch,
    *,
    channels: Sequence[int] | None = None,
    ax=None,
    title: str | None = None,
):
    ax = ax or plt.gca()
    chs = channels or sorted(batch.singles.keys())
    counts = [batch.total_events(ch) for ch in chs]
    ax.bar(chs, counts, color="#3a86ff")
    ax.set_xlabel("Channel")
    ax.set_ylabel("Counts (per chunk)")
    ax.set_title(title or "Singles per channel")
    ax.set_xticks(chs)
    ax.grid(axis="y", alpha=0.2)
    return ax


def plot_coincidences(
    result: CoincidenceResult,
    *,
    labels: Iterable[str] | None = None,
    ax=None,
    title: str | None = None,
):
    ax = ax or plt.gca()
    lbls = list(labels or result.counts.keys())
    values = [result.counts.get(lbl, 0) for lbl in lbls]
    ax.bar(lbls, values, color="#ff006e")
    ax.set_ylabel("Coincidences per chunk")
    ax.set_title(title or "Coincidences")
    ax.grid(axis="y", alpha=0.2)
    return ax


def plot_metrics(values: Sequence[MetricValue], *, ax=None, title: str | None = None):
    ax = ax or plt.gca()
    labels = [val.name for val in values]
    data = [val.value for val in values]
    ax.plot(labels, data, marker="o")
    ax.set_ylim(0, 1)
    ax.set_ylabel("Value")
    ax.set_title(title or "Metric summary")
    ax.grid(True, alpha=0.2)
    return ax


def plot_metric_group(
    values: Sequence[MetricValue],
    *,
    ax=None,
    title: str | None = None,
    ylabel: str | None = None,
):
    ax = ax or plt.gca()
    labels = [val.name for val in values]
    data = [val.value for val in values]
    ax.bar(labels, data, color="#8338ec")
    ax.set_ylim(0, 1)
    ax.set_title(title or "Metrics")
    ax.set_ylabel(ylabel or "Value")
    for i, val in enumerate(data):
        ax.text(i, val + 0.02, f"{val:.3f}", ha="center", fontsize=8)
    ax.grid(axis="y", alpha=0.2)
    return ax
