"""
utils/concentration_metrics.py
==============================
Calcul concentration_ratio, détection pauses.
"""
from datetime import datetime
from typing import List, Dict


class ConcentrationMetrics:
    PAUSE_THRESHOLD_SECONDS = 900

    @classmethod
    def calculate_concentration_ratio(cls, accumulated_seconds: int, planned_duration_minutes: int) -> float:
        if not planned_duration_minutes:
            return 0.0
        planned_seconds = planned_duration_minutes * 60
        return min(1.0, accumulated_seconds / planned_seconds) if planned_seconds > 0 else 0.0

    @classmethod
    def detect_gaps(cls, ping_timestamps: List[datetime]) -> List[Dict]:
        if len(ping_timestamps) < 2:
            return []
        gaps = []
        sorted_pings = sorted(ping_timestamps)
        for i in range(1, len(sorted_pings)):
            delta = int((sorted_pings[i] - sorted_pings[i-1]).total_seconds())
            if delta > cls.PAUSE_THRESHOLD_SECONDS:
                gaps.append({
                    "start": sorted_pings[i-1].isoformat(),
                    "end": sorted_pings[i].isoformat(),
                    "duration_seconds": delta,
                })
        return gaps

    @classmethod
    def estimate_effective_minutes(cls, accumulated_seconds: int, nb_pauses: int) -> float:
        base = accumulated_seconds / 60
        penalty = nb_pauses * 2
        return max(0, base - penalty)
