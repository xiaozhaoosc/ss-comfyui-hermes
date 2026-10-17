# -*- coding: utf-8 -*-
"""Asset Manager server launcher.

Runs the FastAPI backend service via Uvicorn.

Usage:
    python tools/asset_manager/run.py
    python tools/asset_manager/run.py --port 8090 --host 127.0.0.1
"""
import argparse
import sys
import webbrowser
from pathlib import Path

# Fix Windows console UTF-8 encoding
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add backend directory to sys.path
CUR_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CUR_DIR))

import uvicorn
from backend.config import HOST, PORT


def main():
    parser = argparse.ArgumentParser(description="AIGC Local Asset Hub Server")
    parser.add_argument("--host", default=HOST, help=f"Host to bind (default: {HOST})")
    parser.add_argument("--port", type=int, default=PORT, help=f"Port to bind (default: {PORT})")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    parser.add_argument("--no-browser", action="store_true", help="Do not open browser automatically")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    print("=" * 65)
    print(f"🚀 Starting AIGC Local Asset Hub on {url}")
    print(f"📚 API Documentation: {url}/docs")
    print(f"⚡ Zero-VRAM Architecture (Pure CPU Math + ComfyUI 8188 Delegation)")
    print("=" * 65)

    if not args.no_browser:
        import threading
        import time

        def _open_browser():
            time.sleep(0.8)
            try:
                webbrowser.open(url)
            except Exception:
                pass

        threading.Thread(target=_open_browser, daemon=True).start()

    uvicorn.run(
        "backend.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(CUR_DIR),
    )


if __name__ == "__main__":
    main()
