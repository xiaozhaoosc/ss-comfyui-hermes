# -*- coding: utf-8 -*-
"""FastAPI Application Main Module.

Provides RESTful endpoints, static file hosting for character & garment images,
and lifecycle synchronization.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .config import (
    ASSETS_LIB_DIR,
    CHARACTER_LIB_DIR,
    COMFY_INPUT_DIR,
    FRONTEND_DIST_DIR,
    GARMENT_LIB_DIR,
    ROOT_DIR,
)
from .database import SessionLocal, init_db
from .routers import characters, comfy, comfy_assets, combos, garments, publish, system
from .sync_engine import sync_all

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("asset_manager")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: initialize database and perform startup sync."""
    logger.info("Initializing database schema...")
    init_db()

    logger.info("Scanning library assets from disk...")
    db = SessionLocal()
    try:
        counts = sync_all(db)
        logger.info(f"Startup sync completed: {counts}")
    finally:
        db.close()

    yield
    logger.info("Shutting down Asset Manager backend...")


app = FastAPI(
    title="AIGC Local Asset Hub API",
    description="High-performance, zero-VRAM asset management backend for ComfyUI",
    version="1.0.0",
    lifespan=lifespan,
)

# Enable CORS for local web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount local static directories for high-speed image loading
if CHARACTER_LIB_DIR.exists():
    app.mount(
        "/static/characters",
        StaticFiles(directory=str(CHARACTER_LIB_DIR)),
        name="character_static",
    )

if GARMENT_LIB_DIR.exists():
    app.mount(
        "/static/garments",
        StaticFiles(directory=str(GARMENT_LIB_DIR)),
        name="garment_static",
    )

if ASSETS_LIB_DIR.exists():
    app.mount(
        "/static/assets",
        StaticFiles(directory=str(ASSETS_LIB_DIR)),
        name="assets_static",
    )

OUTPUT_DIR = ROOT_DIR / "output"
if OUTPUT_DIR.exists():
    app.mount(
        "/static/output",
        StaticFiles(directory=str(OUTPUT_DIR)),
        name="output_static",
    )

if COMFY_INPUT_DIR.exists():
    app.mount(
        "/static/input",
        StaticFiles(directory=str(COMFY_INPUT_DIR)),
        name="input_static",
    )

# Register API routers
app.include_router(characters.router)
app.include_router(garments.router)
app.include_router(combos.router)
app.include_router(system.router)
app.include_router(comfy.router)
app.include_router(publish.router)
app.include_router(comfy_assets.router)

# Mount frontend build artifacts if dist/ exists
if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "index.html").exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST_DIR), html=True), name="frontend")
else:
    @app.get("/")
    def index_fallback():
        return {
            "name": "AIGC Local Asset Hub API",
            "status": "online",
            "docs_url": "/docs",
            "stats_url": "/api/system/stats",
        }

