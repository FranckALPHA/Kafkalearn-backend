from datetime import datetime, timezone

def normaliser_date(date_str: str) -> datetime:
    """Normalise une date ISO en datetime UTC aware."""
    dt = datetime.fromisoformat(date_str)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt
