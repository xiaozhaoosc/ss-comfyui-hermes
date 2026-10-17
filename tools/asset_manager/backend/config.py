# -*- coding: utf-8 -*-
"""Asset Manager Configuration Module."""
import os
from pathlib import Path

# Base Paths
BACKEND_DIR = Path(__file__).resolve().parent
ASSET_MANAGER_DIR = BACKEND_DIR.parent
ROOT_DIR = ASSET_MANAGER_DIR.parent.parent

# Library Paths
CHARACTER_LIB_DIR = ROOT_DIR / "character_library"
COMFY_INPUT_DIR = ROOT_DIR / "input"
COMFY_OUTPUT_DIR = ROOT_DIR / "output"
GARMENT_LIB_DIR = ROOT_DIR / "garment_library"
ASSETS_LIB_DIR = ROOT_DIR / "assets"

# Database Path
DB_PATH = ASSET_MANAGER_DIR / "assets.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# Static Frontend Dist
FRONTEND_DIST_DIR = ASSET_MANAGER_DIR / "dist"

# Server Settings
HOST = os.getenv("ASSET_MANAGER_HOST", "127.0.0.1")
PORT = int(os.getenv("ASSET_MANAGER_PORT", "8090"))
COMFYUI_URL = os.getenv("COMFYUI_URL", "http://127.0.0.1:8188")
