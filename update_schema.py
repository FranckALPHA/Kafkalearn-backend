import sys
import os
sys.path.append(os.getcwd())

from app.core.database import engine
from sqlalchemy import text

def update():
    try:
        with engine.begin() as conn:
            print("[*] Ajout de la colonne is_deleted...")
            conn.execute(text("ALTER TABLE pedagogical_assets ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_pedagogical_assets_is_deleted ON pedagogical_assets(is_deleted);"))
            conn.execute(text("ALTER TABLE calendar_sessions ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_calendar_sessions_is_deleted ON calendar_sessions(is_deleted);"))
            conn.execute(text("ALTER TABLE calendar_timetable ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_calendar_timetable_is_deleted ON calendar_timetable(is_deleted);"))
            print("[+] Colonne et index ajoutés avec succès.")
    except Exception as e:
        print(f"[-] Erreur: {e}")

if __name__ == "__main__":
    update()
