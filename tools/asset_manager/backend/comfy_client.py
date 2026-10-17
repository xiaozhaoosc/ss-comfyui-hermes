# -*- coding: utf-8 -*-
"""ComfyUI API Client and Delegation Proxy.

Enables zero-VRAM delegation from the Asset Hub to the running ComfyUI (8188)
instance for heavy GPU tasks (SAM2 garment cutout, VTON try-on, face-swap).
"""
import json
import logging
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

from .config import COMFYUI_URL

logger = logging.getLogger(__name__)


class ComfyClient:
    """HTTP client communicating with ComfyUI REST API."""

    def __init__(self, base_url: str = COMFYUI_URL):
        self.base_url = base_url.rstrip("/")

    def is_alive(self) -> bool:
        """Check if ComfyUI server is reachable on port 8188."""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def get_system_stats(self) -> Optional[Dict[str, Any]]:
        """Fetch GPU/VRAM and execution status from ComfyUI."""
        try:
            req = urllib.request.Request(f"{self.base_url}/system_stats", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Failed to fetch system stats from ComfyUI: {e}")
            return None

    def get_queue(self) -> Optional[Dict[str, Any]]:
        """Fetch running and pending queue counts."""
        try:
            req = urllib.request.Request(f"{self.base_url}/queue", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            logger.warning(f"Failed to fetch queue from ComfyUI: {e}")
            return None

    def queue_prompt(self, prompt_graph: Dict[str, Any], client_id: str = "asset_hub") -> Optional[str]:
        """Submit an execution graph prompt to ComfyUI. Returns prompt_id."""
        payload = json.dumps({"prompt": prompt_graph, "client_id": client_id}).encode("utf-8")
        try:
            req = urllib.request.Request(
                f"{self.base_url}/prompt",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                res = json.loads(resp.read().decode("utf-8"))
                return res.get("prompt_id")
        except Exception as e:
            logger.error(f"Failed to queue prompt to ComfyUI: {e}")
            return None


comfy_client = ComfyClient()
