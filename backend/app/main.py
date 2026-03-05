# =============================================================================
# app/main.py
# Purpose : FastAPI application entry point. Initialises the app, registers
#           middleware, mounts the router, and serves the frontend statically.
# =============================================================================

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.routes import router
import os

# -----------------------------------------------------------------------------
# Logging — INFO level so latency logs from engine.py are visible in terminal
# -----------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# App Initialisation
# -----------------------------------------------------------------------------
app = FastAPI(
    title       = "Daraz Shopping Assistant API",
    description = "CPU-optimised local LLM backend for NLP Assignment.",
    version     = "1.0.0",
    docs_url    = "/docs",   # Swagger UI — use this to test without frontend
    redoc_url   = "/redoc",  # Alternative API docs
)

# -----------------------------------------------------------------------------
# CORS Middleware
# Allows the frontend (served on port 3000 via nginx) to call the backend
# (port 8000). Allow all origins during development — tighten for production.
# -----------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins     = ["*"],
    allow_credentials = True,
    allow_methods     = ["*"],
    allow_headers     = ["*"],
)

# -----------------------------------------------------------------------------
# Register API Router
# All routes defined in routes.py are mounted here under no prefix so
# /chat, /ws/chat, /reset, /health are all top-level.
# -----------------------------------------------------------------------------
app.include_router(router)

# -----------------------------------------------------------------------------
# Health Check
# First thing to hit when testing — if this returns {"status": "ok"} your
# server is up and the model has been imported (though not yet warmed up).
# -----------------------------------------------------------------------------
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "model": "qwen2.5-1.5b-instruct-q4_k_m"}

# -----------------------------------------------------------------------------
# Serve Frontend Statically (for when your partner's UI is ready)
# The nginx container in docker-compose handles this in production.
# This block lets you serve the frontend directly from uvicorn during local dev
# WITHOUT modifying any frontend files.
# -----------------------------------------------------------------------------
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount(
        "/static",
        StaticFiles(directory=FRONTEND_DIR),
        name="static"
    )
    logger.info(f"Frontend static files mounted from: {FRONTEND_DIR}")

    @app.get("/ui", tags=["Frontend"])
    async def serve_frontend():
        """Serves the frontend index.html directly from uvicorn for local dev."""
        index_path = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index_path):
            return FileResponse(index_path)
        return {"message": "Frontend not built yet. index.html not found."}