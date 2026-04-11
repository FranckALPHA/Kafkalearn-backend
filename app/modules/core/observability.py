"""
modules/core/observability.py
=============================
Logging structuré JSON + Métriques in-memory.
"""
import json
import logging
import sys
from datetime import datetime
from collections import defaultdict

class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry)


def setup_logging():
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger


logger = setup_logging()


class MetricsCollector:
    """Collecteur de métriques in-memory simple."""

    def __init__(self):
        self._counters = defaultdict(int)
        self._timings = defaultdict(list)

    def increment(self, key: str, value: int = 1):
        self._counters[key] += value

    def record_timing(self, key: str, ms: float):
        self._timings[key].append(ms)
        if len(self._timings[key]) > 1000:
            self._timings[key] = self._timings[key][-500:]

    def get_counter(self, key: str) -> int:
        return self._counters.get(key, 0)

    def get_avg_timing(self, key: str) -> float:
        timings = self._timings.get(key, [])
        return sum(timings) / len(timings) if timings else 0.0

    def get_all(self) -> dict:
        return {
            "counters": dict(self._counters),
            "avg_timings": {k: self.get_avg_timing(k) for k in self._timings},
        }


metrics = MetricsCollector()
