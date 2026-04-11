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

app.include_router(users_router, prefix="/api/v1")
app.include_router(search_router, prefix="/api/v1")


# ─── Routes ──────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def accueil():
    return f"""
    <html>
    <head><title>KafkaLearn Backend</title></head>
    <body>
        <h1>KafkaLearn Backend v{APP_VERSION}</h1>
        <p>Modules actifs : Users, Search</p>
        <p><a href="/docs">Documentation Swagger UI</a></p>
    </body>
    </html>
    """


@app.get("/health")
async def health():
    return {"status": "ok", "version": APP_VERSION}
