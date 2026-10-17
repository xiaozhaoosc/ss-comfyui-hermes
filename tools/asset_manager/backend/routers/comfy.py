# -*- coding: utf-8 -*-
"""ComfyUI integration and workflow proxy router."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..comfy_client import comfy_client

router = APIRouter(prefix="/api/comfy", tags=["ComfyUI Delegation"])


class PromptDispatchPayload(BaseModel):
    prompt: Dict[str, Any]
    client_id: Optional[str] = "asset_hub"


@router.get("/status")
def get_comfy_status():
    """Check connectivity and fetch queue/system stats from ComfyUI 8188."""
    alive = comfy_client.is_alive()
    if not alive:
        return {
            "online": False,
            "url": comfy_client.base_url,
            "message": "ComfyUI is offline or unreachable at 8188",
        }

    stats = comfy_client.get_system_stats()
    queue = comfy_client.get_queue()

    return {
        "online": True,
        "url": comfy_client.base_url,
        "stats": stats,
        "queue": queue,
    }


@router.post("/dispatch")
def dispatch_workflow(payload: PromptDispatchPayload):
    """Proxy submit a workflow prompt graph to ComfyUI 8188."""
    if not comfy_client.is_alive():
        raise HTTPException(
            status_code=503,
            detail="ComfyUI server is offline. Please launch ComfyUI on port 8188.",
        )

    prompt_id = comfy_client.queue_prompt(payload.prompt, client_id=payload.client_id)
    if not prompt_id:
        raise HTTPException(status_code=500, detail="Failed to queue prompt to ComfyUI.")

    return {"status": "dispatched", "prompt_id": prompt_id}
