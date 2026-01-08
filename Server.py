"""QLaibLab socket server using qlaiblib backends.

Commands:
  - "GATHER DATA": capture a chunk and return singles + coincidences
  - "EXPOSURE{seconds}": update exposure time
  - "STOP": close server
"""

from __future__ import annotations

import socket
from dataclasses import dataclass
from typing import Dict, Iterable, Tuple

from qlaiblib.acquisition.qutag import QuTAGBackend
from qlaiblib.coincidence.delays import (
    DEFAULT_REF_PAIRS,
    DEFAULT_CROSS_PAIRS,
    auto_calibrate_delays,
    specs_from_delays,
)
from qlaiblib.coincidence.pipeline import CoincidencePipeline


@dataclass
class ServerConfig:
    host: str = "141.255.216.170"
    port: int = 65432
    exposure_sec: float = 5.0
    window_ps: float = 250.0
    delay_start_ps: float = -30000.0
    delay_end_ps: float = 30000.0
    delay_step_ps: float = 10.0
    ref_pairs: Tuple[Tuple[str, int, int], ...] = DEFAULT_REF_PAIRS
    cross_pairs: Tuple[Tuple[str, int, int], ...] = DEFAULT_CROSS_PAIRS
    singles_channels: Tuple[int, ...] = (5, 6, 7, 8)
    include_accidentals: bool = False


def _calibrate_pipeline(
    backend: QuTAGBackend, cfg: ServerConfig
) -> CoincidencePipeline:
    batch = backend.capture(cfg.exposure_sec)
    delays = auto_calibrate_delays(
        batch,
        pairs=cfg.ref_pairs,
        window_ps=cfg.window_ps,
        delay_start_ps=cfg.delay_start_ps,
        delay_end_ps=cfg.delay_end_ps,
        delay_step_ps=cfg.delay_step_ps,
    )
    specs = specs_from_delays(
        window_ps=cfg.window_ps,
        like_pairs=cfg.ref_pairs,
        cross_pairs=cfg.cross_pairs,
        delays_ps=delays,
    )
    return CoincidencePipeline(specs, compute_accidentals=cfg.include_accidentals)


def _format_payload(
    singles: Dict[int, int],
    coincidences: Dict[str, int],
    accidentals: Dict[str, float] | None,
) -> str:
    parts: list[str] = []
    for ch in sorted(singles):
        parts.append(f"Channel{ch}: {singles[ch]}")
    for label in coincidences:
        parts.append(f"{label}: {coincidences[label]}")
    if accidentals:
        for label in accidentals:
            parts.append(f"{label}_acc: {accidentals[label]:.2f}")
    return ", ".join(parts)


def server(cfg: ServerConfig) -> None:
    backend = QuTAGBackend(exposure_sec=cfg.exposure_sec)
    pipeline = _calibrate_pipeline(backend, cfg)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((cfg.host, cfg.port))
        s.listen()
        run = True
        print(f"Server listening on {cfg.host}:{cfg.port}")
        try:
            while run:
                conn, addr = s.accept()
                with conn:
                    print("Connected by", addr)
                    conn.settimeout(5)
                    while True:
                        try:
                            data = conn.recv(1024)
                            if not data:
                                break
                            command = data.decode("utf-8").strip()
                            if command == "GATHER DATA":
                                batch = backend.capture()
                                singles = {
                                    ch: batch.total_events(ch)
                                    for ch in cfg.singles_channels
                                }
                                result = pipeline.run(batch)
                                payload = _format_payload(
                                    singles,
                                    result.counts,
                                    result.accidentals
                                    if cfg.include_accidentals
                                    else None,
                                )
                                conn.sendall(payload.encode("utf-8"))
                            elif command == "STOP":
                                run = False
                                conn.sendall(b"Ending recording now.")
                                break
                            elif command.startswith("EXPOSURE"):
                                exposure_str = command[8:].strip()
                                try:
                                    cfg.exposure_sec = float(exposure_str)
                                    backend.set_exposure(cfg.exposure_sec)
                                    conn.sendall(
                                        f"Exposure time is {cfg.exposure_sec} s.".encode(
                                            "utf-8"
                                        )
                                    )
                                except ValueError:
                                    conn.sendall(b"Invalid exposure time value.")
                            else:
                                conn.sendall(b"Unknown command")
                        except socket.timeout:
                            print("Timeout occurred, no data received.")
                            break
                        except socket.error as exc:
                            print(f"Socket error: {exc}")
                            break
        finally:
            backend.close()


if __name__ == "__main__":
    server(ServerConfig())
