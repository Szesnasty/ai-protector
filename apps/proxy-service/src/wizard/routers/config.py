"""Config generation router (Agent Wizard — spec 28e)."""

from __future__ import annotations

import io
import uuid
import zipfile
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.session import get_db
from src.wizard.models import Agent
from src.wizard.services.config_gen import (
    generate_limits_yaml,
    generate_policy_yaml,
    generate_rbac_yaml,
)
from src.wizard.services.policy_packs import get_policy_pack, list_policy_packs

logger = structlog.get_logger()

router = APIRouter(prefix="/agents/{agent_id}", tags=["config"])


async def _get_agent_or_404(agent_id: uuid.UUID, db: AsyncSession) -> Agent:
    agent = await db.get(Agent, agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.post("/generate-config", status_code=200)
async def generate_config(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Generate all 3 config files and cache on agent record."""
    agent = await _get_agent_or_404(agent_id, db)

    rbac_yaml = await generate_rbac_yaml(agent_id, db)
    limits_yaml = await generate_limits_yaml(agent_id, db)
    policy_yaml = await generate_policy_yaml(agent_id, db)

    generated_at = datetime.now(UTC).isoformat()

    config = {
        "rbac_yaml": rbac_yaml,
        "limits_yaml": limits_yaml,
        "policy_yaml": policy_yaml,
        "generated_at": generated_at,
    }

    agent.generated_config = config
    await db.commit()
    await db.refresh(agent)

    logger.info("config_generated", agent_id=str(agent_id), agent_name=agent.name)
    return config


@router.get("/config")
async def get_config(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> dict:
    """Return the last generated config (cached)."""
    agent = await _get_agent_or_404(agent_id, db)

    if agent.generated_config is None:
        raise HTTPException(status_code=404, detail="No config generated yet. Call POST /generate-config first.")

    return agent.generated_config


@router.get("/config/download")
async def download_config(
    agent_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),  # noqa: B008
) -> StreamingResponse:
    """Download generated config as a .zip with 3 YAML files."""
    agent = await _get_agent_or_404(agent_id, db)

    if agent.generated_config is None:
        raise HTTPException(status_code=404, detail="No config generated yet. Call POST /generate-config first.")

    config = agent.generated_config

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("rbac.yaml", config["rbac_yaml"])
        zf.writestr("limits.yaml", config["limits_yaml"])
        zf.writestr("policy.yaml", config["policy_yaml"])
    buf.seek(0)

    safe_name = agent.name.replace(" ", "_").lower()
    filename = f"{safe_name}_config.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ═══════════════════════════════════════════════════════════════════════
# Policy packs listing (spec 28c)
# ═══════════════════════════════════════════════════════════════════════

packs_router = APIRouter(prefix="/policy-packs", tags=["config"])


@packs_router.get("")
async def list_packs() -> list[dict]:
    """List all available policy packs."""
    return [p.to_dict() for p in list_policy_packs()]


@packs_router.get("/{pack_name}")
async def get_pack(pack_name: str) -> dict:
    """Get a specific policy pack."""
    try:
        pack = get_policy_pack(pack_name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Policy pack '{pack_name}' not found") from None
    return pack.to_dict()
