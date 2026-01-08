"""
Quick checker: shows how counting coincidences per-second (naively) can
under-count pairs that straddle a second boundary, versus counting on the
flattened, globally sorted arrays (what the pipeline does).

Run:
    python scripts/flatten_vs_bins.py
"""

from __future__ import annotations

import numpy as np

from qlaiblib.io import coincfinder_backend as cf


def ground_truth(flat_a: np.ndarray, flat_b: np.ndarray, window_ps: float, delay_ps: float = 0.0) -> int:
    """Reference: count coincidences on fully flattened, sorted arrays."""
    return cf.count_pair(flat_a, flat_b, window_ps=window_ps, delay_ps=delay_ps)


def bin_edges(arr: np.ndarray, bucket_sec: float) -> dict[int, np.ndarray]:
    """Split timestamps (ps) into integer-second buckets; returns sec -> array slice."""
    bucket_ps = int(bucket_sec * 1e12)
    buckets: dict[int, list[int]] = {}
    for ts in arr:
        sec = int(ts // bucket_ps)
        buckets.setdefault(sec, []).append(int(ts))
    return {sec: np.array(vals, dtype=np.int64) for sec, vals in buckets.items()}


def naive_per_second(bins_a: dict[int, np.ndarray], bins_b: dict[int, np.ndarray], window_ps: float, delay_ps: float = 0.0) -> int:
    """Naively sum coincidences per second without handling boundary-crossers."""
    total = 0
    for sec in sorted(set(bins_a) | set(bins_b)):
        a = bins_a.get(sec, np.empty(0, dtype=np.int64))
        b = bins_b.get(sec, np.empty(0, dtype=np.int64))
        total += cf.count_pair(a, b, window_ps=window_ps, delay_ps=delay_ps)
    return total


def demo():
    rng = np.random.default_rng(0)
    bucket_sec = 2.0
    window_ps = 500.0
    # Build two channels with events placed around boundaries (2 s, 4 s) to force cross-boundary coincidences.
    ch_a = np.sort(
        np.concatenate(
            [
                rng.integers(0, 1.8e12, size=300),             # early in sec 0–1
                rng.integers(1.95e12, 2.05e12, size=40),       # straddle boundary 2 s
                rng.integers(3.9e12, 4.05e12, size=40),        # straddle boundary 4 s
                rng.integers(4.2e12, 5.8e12, size=300),
                np.array([1.9999999995e12]),                   # forced cross-boundary hit near 2 s
                np.array([3.9999999995e12]),                   # forced cross-boundary hit near 4 s
            ]
        )
    ).astype(np.int64)
    ch_b = np.sort(
        np.concatenate(
            [
                rng.integers(0, 1.8e12, size=300),
                rng.integers(1.95e12, 2.05e12, size=40),       # straddle boundary 2 s
                rng.integers(3.9e12, 4.05e12, size=40),        # straddle boundary 4 s
                rng.integers(4.2e12, 5.8e12, size=300),
                np.array([2.0000000000e12]),                   # within 500 ps of the above (2 s)
                np.array([4.0000000000e12]),                   # within 500 ps of the above (4 s)
            ]
        )
    ).astype(np.int64)

    # Ground truth on flattened arrays
    gt = ground_truth(ch_a, ch_b, window_ps)

    # Naive per-second sum (ignores boundary-crossers)
    bins_a = bin_edges(ch_a, bucket_sec)
    bins_b = bin_edges(ch_b, bucket_sec)
    naive = naive_per_second(bins_a, bins_b, window_ps)

    print(f"Flattened (ground truth) : {gt}")
    print(f"Naive per-second sum     : {naive}")
    print(f"Missed coincidences      : {gt - naive}")


if __name__ == "__main__":
    demo()
