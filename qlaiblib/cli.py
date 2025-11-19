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
)
from .live.controller import LiveAcquisition
from .metrics import REGISTRY
from .plotting import static as static_plots
from .io import coincfinder_backend as cf_backend

app = typer.Typer(add_completion=False)


def _create_backend(mock: bool, exposure: float):
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
):
    """Capture a single chunk and print singles per channel."""

    backend = _create_backend(mock, exposure)
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
):
    """Measure coincidences + metrics once."""

    backend = _create_backend(mock, exposure)
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
    window_ps: float = typer.Option(200.0, help="Coincidence window in picoseconds."),
    mock: bool = typer.Option(False, help="Use mock backend."),
    delay_start_ps: float = typer.Option(-8_000, help="Delay scan range start (ps)."),
    delay_end_ps: float = typer.Option(8_000, help="Delay scan range end (ps)."),
    delay_step_ps: float = typer.Option(50.0, help="Delay scan step (ps)."),
):
    """Launch the Tkinter live dashboard."""

    backend = _create_backend(mock, exposure)
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
    run_dashboard(controller)


@app.command()
def replay(
    path: Path = typer.Argument(..., exists=True, readable=True, help="Path to BIN file recorded with QuTAG."),
    window_ps: float = typer.Option(200.0, help="Coincidence window in picoseconds."),
    plot: bool = typer.Option(False, help="Plot coincidences + metrics."),
    delay_start_ps: float = typer.Option(-8_000, help="Delay scan range start (ps)."),
    delay_end_ps: float = typer.Option(8_000, help="Delay scan range end (ps)."),
    delay_step_ps: float = typer.Option(50.0, help="Delay scan step (ps)."),
):
    """Process an existing BIN file (≈5 s capture) and report metrics."""

    batch = cf_backend.read_file(path)
    typer.echo(f"Loaded {path} (duration {batch.duration_sec:.2f} s)")
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

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
        static_plots.plot_coincidences(coincidences, ax=ax1)
        static_plots.plot_metrics(metrics, ax=ax2)
        plt.show()


def main():
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
