"""
utils/pricing_calculator.py
===========================
Calcul des tranches tarifaires dégressives pour les écoles.
"""
from typing import Optional, Tuple


class PricingCalculator:
    TIERS = [
        (10, 49, 300),
        (50, 149, 225),
        (150, 499, 175),
        (500, None, None),
    ]
    MIN_SEATS = 10
    QUOTA_IA_PAR_SIEGE = 25

    def calculer_tranche(self, nb_sieges: int) -> str:
        if nb_sieges < self.MIN_SEATS:
            raise ValueError(f"Minimum {self.MIN_SEATS} sièges requis")
        for min_s, max_s, _ in self.TIERS:
            if max_s is None or nb_sieges <= max_s:
                if min_s <= nb_sieges:
                    return f"{min_s}-{max_s if max_s else '+'}"
        return "500+"

    def calculer_prix_par_siege(self, nb_sieges: int) -> Optional[int]:
        for min_s, max_s, prix in self.TIERS:
            if max_s is None or nb_sieges <= max_s:
                if min_s <= nb_sieges:
                    return prix
        return None

    def calculer_prix_mensuel(self, nb_sieges: int) -> Optional[int]:
        prix = self.calculer_prix_par_siege(nb_sieges)
        return nb_sieges * prix if prix is not None else None

    def calculer_quota_ia_journalier(self, nb_sieges: int) -> int:
        return nb_sieges * self.QUOTA_IA_PAR_SIEGE

    def get_exemple_tarif(self, nb_sieges: int) -> str:
        prix = self.calculer_prix_mensuel(nb_sieges)
        tranche = self.calculer_tranche(nb_sieges)
        if prix is None:
            return "Contactez-nous pour un devis personnalisé"
        return f"{nb_sieges} sièges = {prix:,} FCFA/mois (tranche {tranche})"
