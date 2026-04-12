"""
utils/time_utils.py
===================
Helpers timezone, parsing HH:MM, calcul durées.
"""
from datetime import datetime, time, timedelta, timezone
from typing import Optional


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def parse_time(hhmm: str) -> time:
    h, m = hhmm.split(":")
    return time(int(h), int(m))


def duration_minutes(start: datetime, end: datetime) -> float:
    return (end - start).total_seconds() / 60.0


def seconds_to_minutes(seconds: int) -> float:
    return seconds / 60.0


def is_within_window(dt: datetime, window_minutes: int = 15) -> bool:
    return abs((now_utc() - dt).total_seconds()) <= window_minutes * 60
