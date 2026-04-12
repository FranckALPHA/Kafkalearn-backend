class EducationNormalizer:
    MATIERE_MAP = {
        "math": "Mathematiques", "maths": "Mathematiques", "mathematiques": "Mathematiques",
        "phy": "Physique", "physique": "Physique",
        "svt": "SVT", "bio": "SVT",
        "fr": "Francais", "francais": "Francais",
        "hist": "Histoire-Geographie", "histoire": "Histoire-Geographie", "geo": "Histoire-Geographie",
        "philo": "Philosophie",
        "info": "Informatique",
    }
    NIVEAU_MAP = {
        "tle": "Terminale", "terminale": "Terminale",
        "1ere": "Premiere", "premiere": "Premiere",
        "2nde": "Seconde", "seconde": "Seconde",
        "3eme": "3eme", "troisieme": "3eme",
    }

    def normaliser_matiere(self, matiere: str) -> str:
        return self.MATIERE_MAP.get(matiere.lower().strip(), matiere.strip().title())

    def normaliser_niveau(self, niveau: str) -> str:
        return self.NIVEAU_MAP.get(niveau.lower().strip(), niveau.strip().title())
