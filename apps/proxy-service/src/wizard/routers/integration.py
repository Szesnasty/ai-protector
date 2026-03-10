"""Integration kit router (Agent Wizard — spec 29k)."""

from __future__ import annotations

import io
import uuid
import zipfile

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.wizard.models import Agent
from src.wizard.services.integration_kit import _slugify, generate_integration_kit

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/{agent_id}", tags=["integration-kit"])


async def _get_agent_or_404(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/integration-kit", status_code=200)
async def generate_kit(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Generate integration kit (7 files) and cache on agent record."""
    agent = await _get_agent_or_404(agent_id, db)

    try:
        kit = await generate_integration_kit(agent_id, db)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    # Store on agent
    agent.generated_kit = kit
    await db.commit()
    await db.refresh(agent)

    logger.info("integration_kit_generated", agent_id=str(agent_id), framework=kit["framework"])
    return kit


@router.get("/integration-kit")
async def get_kit(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Return last generated integration kit (cached)."""
    agent = await _get_agent_or_404(agent_id, db)

    if agent.generated_kit is None:
        raise HTTPException(
            status_code=404,
            detail="No integration kit generated yet. Call POST /integration-kit first.",
        )

    return agent.generated_kit


@router.get("/integration-kit/download")
async def download_kit(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    """Download integration kit as .zip."""
    agent = await _get_agent_or_404(agent_id, db)

    if agent.generated_kit is None:
        raise HTTPException(
            status_code=404,
            detail="No integration kit generated yet. Call POST /integration-kit first.",
        )

    kit = agent.generated_kit
    files = kit.get("files", {})

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename, content in files.items():
            zf.writestr(filename, content)
    buf.seek(0)

    slug = _slugify(agent.name)
    zip_filename = f"ai-protector-{slug}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
    )
