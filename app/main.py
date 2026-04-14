"""
app/main.py
===========
Point d'entrée de l'API FastAPI - KafkaLearn Backend.
"""

from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env", override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.core.config import APP_VERSION, CORS_ORIGINS, AUTO_CREATE_DB
from app.core.database_init import init_db

# Initialisation de la BDD si demandé
if AUTO_CREATE_DB:
    init_db()

# Création du superadmin par défaut si il n'existe pas
try:
    from app.core.scripts.create_superadmin import create_superadmin
    create_superadmin()
except Exception as e:
    from app.core.config import SUPERADMIN_EMAIL
    print(f"[WARN] Superadmin non créé : {e}")

app = FastAPI(
    title="KafkaLearn Backend",
    description="Backend API pour la plateforme KafkaLearn",
    version=APP_VERSION,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ─────────────────────────────────────────────────────
from app.modules.users.router import router as users_router
from app.modules.search.router import router as search_router
from app.modules.skills.router import router as skills_router
from app.modules.epreuves.router import router as epreuves_router
from app.modules.notifications.router import router as notifications_router
from app.modules.referral.router import router as referral_router
from app.modules.payment.router import router as payment_router
from app.modules.school.router import router as school_router
from app.modules.calendar.router import router as calendar_router
from app.modules.library.router import router as library_router
from app.modules.memory.router import router as memory_router
from app.modules.user_documents.router import router as user_documents_router
from app.modules.doc_analysis.router import router as doc_analysis_router
from app.modules.wisdom.router import router as wisdom_router
from app.modules.daily_quiz.router import router as daily_quiz_router
from app.modules.ingest.router import router as ingest_router

app.include_router(users_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")
app.include_router(skills_router, prefix="/api/v1")
app.include_router(epreuves_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(referral_router, prefix="/api/v1")
app.include_router(payment_router, prefix="/api/v1")
app.include_router(school_router, prefix="/api/v1")
app.include_router(calendar_router, prefix="/api/v1")
app.include_router(library_router, prefix="/api/v1")
app.include_router(memory_router, prefix="/api/v1")
app.include_router(user_documents_router, prefix="/api/v1")
app.include_router(doc_analysis_router, prefix="/api/v1")
app.include_router(wisdom_router, prefix="/api/v1")
app.include_router(daily_quiz_router, prefix="/api/v1")
app.include_router(ingest_router, prefix="/api/v1")


# ─── Routes ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def accueil():
    return (
        """<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KafkaLearn - Plateforme d'Apprentissage</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%); min-height: 100vh; color: #e2e8f0; }
        .container { max-width: 1200px; margin: 0 auto; padding: 40px 20px; }
        .hero { text-align: center; padding: 80px 0; }
        .logo { font-size: 64px; margin-bottom: 20px; }
        .logo span { background: linear-gradient(135deg, #6366f1, #a855f7); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }
        h1 { font-size: 48px; font-weight: 700; margin-bottom: 16px; letter-spacing: -0.02em; }
        .subtitle { font-size: 20px; color: #94a3b8; font-weight: 300; margin-bottom: 40px; }
        .version { display: inline-block; background: #1e293b; border: 1px solid #334155; border-radius: 20px; padding: 8px 20px; font-size: 14px; color: #94a3b8; margin-bottom: 60px; }
        .links { display: flex; gap: 16px; justify-content: center; flex-wrap: wrap; }
        .link { display: inline-flex; align-items: center; gap: 8px; background: #1e293b; border: 1px solid #334155; padding: 16px 32px; border-radius: 12px; text-decoration: none; color: #e2e8f0; font-weight: 500; transition: all 0.2s; }
        .link:hover { background: #334155; border-color: #6366f1; transform: translateY(-2px); }
        .link.primary { background: linear-gradient(135deg, #6366f1, #a855f7); border: none; }
        .link.primary:hover { opacity: 0.9; }
        .modules { margin-top: 80px; }
        .modules h2 { font-size: 24px; font-weight: 600; margin-bottom: 24px; }
        .modules-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; }
        .module { background: #1e293b; border: 1px solid #334155; border-radius: 8px; padding: 16px; font-size: 14px; }
        .module:hover { border-color: #6366f1; }
        footer { margin-top: 80px; text-align: center; color: #64748b; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="hero">
            <div class="logo"><span>📚</span></div>
            <h1>KafkaLearn</h1>
            <p class="subtitle">La plateforme d'apprentissage intelligente</p>
            <div class="version">Version """
        + APP_VERSION
        + """</div>
            <div class="links">
                <a href="/docs" class="link primary">
                    <span>📖</span> Documentation API
                </a>
                <a href="/health" class="link">
                    <span>💚</span> Health Check
                </a>
            </div>
        </div>
        <div class="modules">
            <h2>Modules actifs</h2>
            <div class="modules-grid">
                <div class="module">👥 Users</div>
                <div class="module">🔍 Search</div>
                <div class="module">🧠 Skills</div>
                <div class="module">📝 Epreuves</div>
                <div class="module">🔔 Notifications</div>
                <div class="module">🎁 Referral</div>
                <div class="module">💳 Payment</div>
                <div class="module">🏫 School</div>
                <div class="module">📅 Calendar</div>
                <div class="module">📚 Library</div>
                <div class="module">💾 Memory</div>
                <div class="module">📄 UserDocuments</div>
                <div class="module">📊 DocAnalysis</div>
                <div class="module">💡 Wisdom</div>
                <div class="module">❓ DailyQuiz</div>
                <div class="module">📥 Ingest</div>
            </div>
        </div>
        <footer>
            <p>KafkaLearn Backend - API propulsée par FastAPI</p>
        </footer>
    </div>
</body>
</html>"""
    )


@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}
