"""GET /v1/models — available models catalog."""

from __future__ import annotations

import httpx
import structlog
from fastapi import APIRouter

from src.config import get_settings
from src.llm.providers import EXTERNAL_MODELS
from src.schemas.models import ModelInfo, ModelsResponse

logger = structlog.get_logger()

router = APIRouter(tags=["models"])


async def _fetch_ollama_models() -> list[ModelInfo]:
    """Query Ollama /api/tags for locally available models.

    Returns an empty list on failure (Ollama might be offline).
    """
    settings = get_settings()
    url = f"{settings.ollama_base_url}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            models = []
            for m in data.get("models", []):
                name = m.get("name", "")
                if not name:
                    continue
                # Build human-readable label from Ollama model name
                label = name.split(":")[0].replace("-", " ").title()
                size_tag = name.split(":")[-1] if ":" in name else ""
                if size_tag:
                    label = f"{label} {size_tag.upper()}"
                models.append(
                    ModelInfo(
                        id=f"ollama/{name}",
                        provider="ollama",
                        name=label,
                    )
                )
            return models
    except Exception:
        logger.debug("ollama_tags_unavailable", url=url)
        # Ollama not running — return empty list so no phantom models appear
        return []


@router.get("/v1/models", response_model=ModelsResponse)
async def list_models() -> ModelsResponse:
    """Return catalog of available models.

    Static catalog of well-known external models
    + dynamic Ollama models from the Ollama API.
    External models are always listed — the frontend knows
    which providers have a key stored in browser SessionStorage.

    In demo mode a ``Demo (Mock)`` model is prepended and Ollama
    model fetching is skipped (Ollama is not running).
    """
    settings = get_settings()

    models: list[ModelInfo] = []

    # Demo mock model — always first when in demo mode
    if settings.mode == "demo":
        models.append(ModelInfo(id="demo", provider="mock", name="Demo (Mock)"))

    # External models catalog (always listed)
    models.extend(ModelInfo(**m) for m in EXTERNAL_MODELS)

    # Ollama models — skip in demo mode (Ollama not running)
    if settings.mode != "demo":
        models.extend(await _fetch_ollama_models())

    return ModelsResponse(models=models)
