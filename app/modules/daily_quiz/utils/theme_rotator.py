from datetime import date

THEME_SCHEDULE = {
    0: "histoire_cameroun",
    1: "tech_afrique",
    2: "geographie_cameroun_afrique",
    3: "sciences_nature",
    4: "culture_arts_litterature",
    5: "sport_cameroun",
    6: "culture_generale_mixte",
}

class ThemeRotator:
    @staticmethod
    def get_theme_for_date(target_date: date) -> str:
        return THEME_SCHEDULE.get(target_date.weekday(), "culture_generale_mixte")
