"""Timing helpers."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def format_timestamp(ts: datetime | None) -> str:
    if ts is None:
        return ""
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
