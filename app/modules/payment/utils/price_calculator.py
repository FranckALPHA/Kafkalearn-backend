"""
utils/price_calculator.py
=========================
Calcul des prix plans et tranches ecole.
"""
from typing import Optional
from app.modules.payment.utils.constants import DEFAULT_PRICES, SCHOOL_PRICE_PER_SEAT


class PriceCalculator:
    @staticmethod
    def get_plan_price(plan_id: str) -> Optional[int]:
        return DEFAULT_PRICES.get(plan_id)

    @staticmethod
    def calculer_prix_mensuel(nb_sieges: int) -> Optional[int]:
        """Calcule le prix mensuel pour une ecole selon le nombre de sieges."""
        for (min_s, max_s), price in SCHOOL_PRICE_PER_SEAT.items():
            if min_s <= nb_sieges and (max_s is None or nb_sieges <= max_s):
                return nb_sieges * price
        return None  # Custom pricing needed
