"""Live acquisition control loop."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Callable, List

from ..acquisition.base import AcquisitionBackend
from ..coincidence.pipeline import CoincidencePipeline
from ..data.models import AcquisitionBatch, CoincidenceResult, MetricValue
from ..metrics import REGISTRY


@dataclass
class LiveUpdate:
    batch: AcquisitionBatch
    coincidences: CoincidenceResult
    metrics: List[MetricValue]


class LiveAcquisition:
    def __init__(
        self,
        backend: AcquisitionBackend,
        pipeline: CoincidencePipeline,
        *,
        exposure_sec: float | None = None,
    ):
        self.backend = backend
        self.pipeline = pipeline
        self.exposure_sec = exposure_sec or backend.default_exposure_sec
        self._callbacks: List[Callable[[LiveUpdate], None]] = []
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def subscribe(self, callback: Callable[[LiveUpdate], None]) -> None:
        self._callbacks.append(callback)

    def _emit(self, update: LiveUpdate) -> None:
        for cb in list(self._callbacks):
            try:
                cb(update)
            except Exception as exc:  # pragma: no cover - logging hook
                print(f"[Live] callback failed: {exc}")

    def run_once(self) -> LiveUpdate:
        batch = self.backend.capture(self.exposure_sec)
        coincidences = self.pipeline.run(batch)
        metrics = REGISTRY.compute_all(coincidences)
        update = LiveUpdate(batch=batch, coincidences=coincidences, metrics=metrics)
        self._emit(update)
        return update

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _loop(self):
        while not self._stop.is_set():
            tic = time.perf_counter()
            self.run_once()
            elapsed = time.perf_counter() - tic
            remaining = max(0.0, self.exposure_sec - elapsed)
            if remaining > 0:
                self._stop.wait(timeout=remaining)

    def close(self):
        self.stop()
        self.backend.close()
