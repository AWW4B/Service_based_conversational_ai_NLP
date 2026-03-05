# =============================================================================
# app/main.py
# Purpose : FastAPI app initialisation with production middleware,
#           lifespan management, and frontend static serving.
# =============================================================================

import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router

# =============================================================================
# LOGGING
# =============================================================================
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# LIFESPAN — startup and shutdown events
# Replaces deprecated @app.on_event("startup")
# =============================================================================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("🚀 Daraz Assistant starting up...")
    # Model is loaded at import time in engine.py (module-level singleton).
    # Nothing extra needed here — just log confirmation.
    logger.info("✅ Startup complete. API ready.")
    yield
    # --- Shutdown ---
    logger.info("🛑 Daraz Assistant shutting down...")


# =============================================================================
# APP
# =============================================================================
app = FastAPI(
    title       = "Daraz Shopping Assistant API",
    description = (
        "CPU-optimised local LLM backend for NLP Assignment. "
        "Uses Qwen2.5-3B-Instruct-Q4_K_M running via llama-cpp-python. "
        "No RAG, no tools — pure prompt engineering and context management."
    ),
    version     = "1.0.0",
    docs_url    = "/docs",    # Swagger UI — use for manual testing
    redoc_url   = "/redoc",
    lifespan    = lifespan,
)


# =============================================================================
# MIDDLEWARE
# =============================================================================

# CORS — allows frontend (port 3000) to call backend (port 8000)
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],   # tighten to ["http://localhost:3000"] in production
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)


# =============================================================================
# ROUTES
# =============================================================================
app.include_router(router)


# =============================================================================
# FRONTEND STATIC SERVING
# In production: nginx container handles this (docker-compose.yml).
# In local dev: uvicorn serves frontend directly so you don't need nginx.
# Your partner's files in frontend/ are served at /ui and /static/*
# without any changes to their code.
# =============================================================================
FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
)

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
    logger.info(f"Frontend mounted from: {FRONTEND_DIR}")

    @app.get("/ui", tags=["Frontend"], include_in_schema=False)
    async def serve_ui():
        """Serves frontend index.html for local dev without nginx."""
        index = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"message": "Frontend not ready yet — index.html not found."}