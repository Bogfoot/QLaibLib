"""Command-line interface for QLaibLib."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict

import typer

from . import (
    CoincidencePipeline,
    CoincidenceSpec,
    MockBackend,
    QuTAGBackend,
    auto_calibrate_delays,
    run_dashboard,
    specs_from_delays,
    DEFAULT_SPECS,
)
from .acquisition.file_replay import FileReplayBackend
from .live.controller import LiveAcquisition
from .metrics import REGISTRY
from .plotting import static as static_plots
from .plotting import timeseries as ts_plots
from .io import coincfinder_backend as cf_backend

app = typer.Typer(add_completion=False)


def _group_metrics(values):
    visibility = [m for m in values if m.name.lower().startswith("visibility")]
    qber = [m for m in values if m.name.lower().startswith("qber")]
    other = [m for m in values if m not in (*visibility, *qber)]
    groups = [
        ("Visibility", visibility),
        ("QBER", qber),
    ]
    if other:
        groups.append(("Other", other))
    return [(name, vals) for name, vals in groups if vals]


def _create_backend(mock: bool, exposure: float, *, demo_file: Path | None = None, bucket_seconds: float | None = None):
    if demo_file:
        return FileReplayBackend(demo_file, exposure_sec=exposure, bucket_seconds=bucket_seconds)
    if mock:
        return MockBackend(exposure_sec=exposure)
    return QuTAGBackend(exposure_sec=exposure)


def _calibrate(
    backend,
    *,
    window_ps: float,
    delay_start_ps: float,
    delay_end_ps: float,
    delay_step_ps: float,
) -> Dict[str, float]:
    batch = backend.capture()
    typer.echo("Calibrating delays...")
    return auto_calibrate_delays(
        batch,
        window_ps=window_ps,
        delay_start_ps=delay_start_ps,
        delay_end_ps=delay_end_ps,
        delay_step_ps=delay_step_ps,
    )


def _calibrate_from_batch(
    batch,
    *,
    window_ps: float,
    delay_start_ps: float,
    delay_end_ps: float,
    delay_step_ps: float,
):
    return auto_calibrate_delays(
        batch,
        window_ps=window_ps,
        delay_start_ps=delay_start_ps,
        delay_end_ps=delay_end_ps,
        delay_step_ps=delay_step_ps,
    )


@app.command()
def count(
    exposure: float = typer.Option(1.0, help="Exposure / integration time per chunk."),
    plot: bool = typer.Option(False, help="Show a Matplotlib bar plot of singles."),
    mock: bool = typer.Option(False, help="Use mock backend instead of QuTAG."),
    demo_file: Path | None = typer.Option(None, help="Replay this BIN file instead of live hardware."),
    bucket_seconds: float | None = typer.Option(None, help="Bucket duration (s) when replaying a file."),
):
    """Capture a single chunk and print singles per channel."""

    backend = _create_backend(mock, exposure, demo_file=demo_file, bucket_seconds=bucket_seconds)
    batch = backend.capture(exposure)
    typer.echo("Channel\tCounts")
    for ch in sorted(batch.singles):
        typer.echo(f"{ch}\t{batch.total_events(ch)}")
    if plot:
        import matplotlib.pyplot as plt

        static_plots.plot_singles(batch)
        plt.show()


@app.command()
def coincide(
    exposure: float = typer.Option(1.0, help="Exposure / integration time per chunk."),
    window_ps: float = typer.Option(200.0, help="Coincidence window in picoseconds."),
    mock: bool = typer.Option(False, help="Use mock backend."),
    plot: bool = typer.Option(False, help="Plot coincidence bars and metric summary."),
    delay_start_ps: float = typer.Option(-8_000, help="Delay scan range start (ps)."),
    delay_end_ps: float = typer.Option(8_000, help="Delay scan range end (ps)."),
    delay_step_ps: float = typer.Option(50.0, help="Delay scan step (ps)."),
    demo_file: Path | None = typer.Option(None, help="Replay BIN file instead of hardware."),
    bucket_seconds: float | None = typer.Option(None, help="Bucket duration (s) for replay."),
):
    """Measure coincidences + metrics once."""

    backend = _create_backend(mock, exposure, demo_file=demo_file, bucket_seconds=bucket_seconds)
    delays = _calibrate(
        backend,
        window_ps=window_ps,
        delay_start_ps=delay_start_ps,
        delay_end_ps=delay_end_ps,
        delay_step_ps=delay_step_ps,
    )
    specs = specs_from_delays(
        window_ps=window_ps,
        delays_ps=delays,
    )
    pipeline = CoincidencePipeline(specs)
    batch = backend.capture(exposure)
    coincidences = pipeline.run(batch)
    metrics = REGISTRY.compute_all(coincidences)
    typer.echo("Label\tCounts\tAccidentals")
    for label in pipeline.labels():
        typer.echo(
            f"{label}\t{coincidences.counts.get(label, 0)}\t{coincidences.accidentals.get(label, 0):.2f}"
        )
    for metric in metrics:
        typer.echo(f"{metric.name}: {metric.value:.4f}")
    if plot:
        import matplotlib.pyplot as plt

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        static_plots.plot_coincidences(coincidences, ax=ax1)
        static_plots.plot_metrics(metrics, ax=ax2)
        plt.show()


@app.command()
def live(
    exposure: float = typer.Option(1.0, help="Exposure / integration time per chunk."),
    window_ps: float = typer.Option(250.0, help="Coincidence window in picoseconds."),
    mock: bool = typer.Option(False, help="Use mock backend."),
    delay_start_ps: float = typer.Option(-20_000, help="Delay scan range start (ps)."),
    delay_end_ps: float = typer.Option(20_000, help="Delay scan range end (ps)."),
    delay_step_ps: float = typer.Option(10.0, help="Delay scan step (ps)."),
    demo_file: Path | None = typer.Option(None, help="Replay this BIN file instead of live hardware."),
    bucket_seconds: float | None = typer.Option(None, help="Bucket duration (s) in demo mode."),
    history_points: int = typer.Option(200, help="Number of points to retain in time series."),
):
    """Launch the Tkinter live dashboard."""

    backend = _create_backend(mock, exposure, demo_file=demo_file, bucket_seconds=bucket_seconds)
    delays = _calibrate(
        backend,
        window_ps=window_ps,
        delay_start_ps=delay_start_ps,
        delay_end_ps=delay_end_ps,
        delay_step_ps=delay_step_ps,
    )
    specs = specs_from_delays(
        window_ps=window_ps,
        delays_ps=delays,
    )
    pipeline = CoincidencePipeline(specs)
    controller = LiveAcquisition(backend, pipeline, exposure_sec=exposure)
    run_dashboard(controller, history_points=history_points)


@app.command()
def replay(
    path: Path = typer.Argument(..., exists=True, readable=True, help="Path to BIN file recorded with QuTAG."),
    window_ps: float = typer.Option(250.0, help="Coincidence window in picoseconds."),
    plot: bool = typer.Option(False, help="Plot coincidences + metrics."),
    delay_start_ps: float = typer.Option(-20_000, help="Delay scan range start (ps)."),
    delay_end_ps: float = typer.Option(20_000, help="Delay scan range end (ps)."),
    delay_step_ps: float = typer.Option(10.0, help="Delay scan step (ps)."),
    timeseries: bool = typer.Option(False, help="Plot singles + coincidences time-series."),
    timeseries_chunk: float | None = typer.Option(None, help="Chunk size (s) for time-series plot (default 1 s, or exposure time if <=0)."),
    bucket_seconds: float | None = typer.Option(None, help="Bucket duration (s) to use when ingesting the BIN (default 1 s, or exposure)."),
    use_default_specs: bool = typer.Option(False, help="Skip auto calibration and use DEFAULT_SPECS."),
):
    """Process an existing BIN file (≈5 s capture) and report metrics."""

    batch = cf_backend.read_file(path, bucket_seconds=bucket_seconds)
    typer.echo(f"Loaded {path} (duration {batch.duration_sec:.2f} s)")
    if use_default_specs:
        specs = DEFAULT_SPECS
    else:
        delays = _calibrate_from_batch(
            batch,
            window_ps=window_ps,
            delay_start_ps=delay_start_ps,
            delay_end_ps=delay_end_ps,
            delay_step_ps=delay_step_ps,
        )
        specs = specs_from_delays(window_ps=window_ps, delays_ps=delays)
    pipeline = CoincidencePipeline(specs)
    coincidences = pipeline.run(batch)
    metrics = REGISTRY.compute_all(coincidences)
    typer.echo("Label\tCounts\tAccidentals")
    for label in pipeline.labels():
        typer.echo(
            f"{label}\t{coincidences.counts.get(label, 0)}\t{coincidences.accidentals.get(label, 0):.2f}"
        )
    for metric in metrics:
        typer.echo(f"{metric.name}: {metric.value:.4f}")
    if plot:
        import matplotlib.pyplot as plt

        metric_groups = _group_metrics(metrics)

        fig = plt.figure(figsize=(12, 7))
        gs = fig.add_gridspec(2, 2, width_ratios=[2, 1])
        ax_coinc = fig.add_subplot(gs[:, 0])
        static_plots.plot_coincidences(coincidences, ax=ax_coinc)
        ax_coinc.set_title("Coincidences summary")
        metric_axes = [fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, 1])]
        for ax in metric_axes:
            ax.axis("off")
        for ax, (group_name, group_values) in zip(metric_axes, metric_groups):
            static_plots.plot_metric_group(
                group_values,
                ax=ax,
                title=f"{group_name} metrics",
                ylabel=group_name,
            )
            ax.axis("on")
        plt.tight_layout()

        if timeseries:
            chunk = timeseries_chunk if timeseries_chunk and timeseries_chunk > 0 else None
            ts = ts_plots.compute_timeseries(batch, chunk, specs)
            fig_ts = plt.figure(figsize=(12, 9))
            gs_ts = fig_ts.add_gridspec(3, 2, height_ratios=[1, 1, 1])
            ax_singles = fig_ts.add_subplot(gs_ts[0, :])
            ax_coinc_ts = fig_ts.add_subplot(gs_ts[1, :])
            metric_axes_ts = [fig_ts.add_subplot(gs_ts[2, 0]), fig_ts.add_subplot(gs_ts[2, 1])]
            for ax in metric_axes_ts:
                ax.axis("off")
            metric_group_names = [
                (name, [val.name for val in group]) for name, group in metric_groups[:2]
            ]
            ts_plots.plot_timeseries(
                ts,
                singles_ax=ax_singles,
                coincid_ax=ax_coinc_ts,
                metric_axes=metric_axes_ts,
                metric_groups=metric_group_names,
            )
            ax_coinc_ts.set_xlabel("Time (s)")
            for ax in metric_axes_ts[: len(metric_group_names)]:
                ax.axis("on")
                ax.set_xlabel("Time (s)")

        plt.show()


def main():
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
