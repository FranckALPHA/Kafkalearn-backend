"""
utils/quiet_hours_checker.py
=============================
Utility to check if a given time falls within quiet hours.
"""
from datetime import time as dt_time
from typing import Optional


class QuietHoursChecker:
    """Handles quiet hour logic including midnight crossing."""

    @staticmethod
    def is_quiet_hour(
        heure_debut: Optional[dt_time],
        heure_fin: Optional[dt_time],
        check_time=None,
    ) -> bool:
        """Return True if check_time falls within the quiet period.

        Handles midnight crossing (e.g. 22:00 -> 07:00).
        """
        if heure_debut is None or heure_fin is None:
            return False

        if check_time is None:
            from datetime import datetime
            check_time = datetime.now().time()

        if not isinstance(check_time, dt_time):
            check_time = check_time.time() if hasattr(check_time, "time") else check_time

        # Midnight crossing: debut > fin (e.g. 22:00 -> 07:00)
        if heure_debut <= heure_fin:
            # Normal range: both on same side of midnight
            return heure_debut <= check_time <= heure_fin
        else:
            # Crosses midnight: quiet if >= debut OR <= fin
            return check_time >= heure_debut or check_time <= heure_fin
