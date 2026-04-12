"""
app/main.py
===========
Point d'entrée de l'API FastAPI - KafkaLearn Backend.
"""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from app.core.config import APP_VERSION, CORS_ORIGINS, AUTO_CREATE_DB
from app.core.database_init import init_db

# Initialisation de la BDD si demandé
if AUTO_CREATE_DB:
    init_db()

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


# ─── Routes ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def accueil():
    return f"""
    <html>
    <head><title>KafkaLearn Backend</title></head>
    <body>
        <h1>KafkaLearn Backend v{APP_VERSION}</h1>
        <p>Modules actifs : Users, Search, Skills, Epreuves, Notifications, Referral, Payment, School, Calendar, Library, Memory, UserDocuments, DocAnalysis, Wisdom</p>
        <p><a href="/docs">Documentation Swagger UI</a></p>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}
