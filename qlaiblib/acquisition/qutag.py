"""QuTAG acquisition backend."""

from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Optional

from .base import AcquisitionBackend
from ..data.models import AcquisitionBatch
from ..io import coincfinder_backend as cf_backend
from ..utils import timing


class QuTAGBackend(AcquisitionBackend):
    def __init__(self, exposure_sec: float = 1.0):
        try:
            import QuTAG_MC as qtag  # type: ignore
        except ImportError as exc:  # pragma: no cover - hw dependency
            raise RuntimeError("QuTAG_MC is not installed.") from exc
        self._driver = qtag.QuTAG()
        self.default_exposure_sec = exposure_sec
        self._lock = threading.Lock()
        self._update_exposure(exposure_sec)

    def _update_exposure(self, exposure_sec: float):
        exposure_ms = max(1, int(exposure_sec * 1000))
        self._driver.setExposureTime(exposure_ms)

    def set_exposure(self, exposure_sec: float) -> None:
        self.default_exposure_sec = exposure_sec
        self._update_exposure(exposure_sec)

    def capture(self, exposure_sec: float | None = None) -> AcquisitionBatch:
        duration = exposure_sec or self.default_exposure_sec
        with self._lock:
            handle = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
            handle.close()
            path = handle.name
            try:
                self._driver.writeTimestamps(path, self._driver.FILEFORMAT_BINARY)
                time.sleep(duration)
                self._driver.writeTimestamps("", self._driver.FILEFORMAT_NONE)
            finally:
                # ensure recording stops on exceptions
                try:
                    self._driver.writeTimestamps("", self._driver.FILEFORMAT_NONE)
                except Exception:
                    pass
        try:
            batch = cf_backend.read_file(path, bucket_seconds=duration)
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass
        batch.metadata.setdefault("exposure_sec", duration)
        batch.metadata.setdefault("captured_at", timing.utc_now().isoformat())
        return batch

    def record_raw(self, path: str, duration: float) -> None:
        duration = max(0.1, duration)
        with self._lock:
            self._driver.writeTimestamps(path, self._driver.FILEFORMAT_BINARY)
            try:
                time.sleep(duration)
            finally:
                self._driver.writeTimestamps("", self._driver.FILEFORMAT_NONE)

    def device_params(self):  # pragma: no cover - thin wrapper
        return self._driver.getDeviceParams()

    def close(self) -> None:  # pragma: no cover - hardware cleanup
        try:
            self._driver.writeTimestamps("", self._driver.FILEFORMAT_NONE)
        finally:
            self._driver.deInitialize()
