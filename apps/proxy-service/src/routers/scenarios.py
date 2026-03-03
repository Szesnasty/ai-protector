"""Attack-scenario catalogue — serves JSON files from data/scenarios/."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException

from src.schemas.scenarios import ScenarioGroup

router = APIRouter(prefix="/scenarios", tags=["scenarios"])

_DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "scenarios"

CatalogueKind = Literal["playground", "agent"]


@lru_cache(maxsize=4)
def _load_catalogue(kind: str) -> list[dict]:
    """Read & cache a scenario JSON file.  Cached forever (restart to reload)."""
    path = _DATA_DIR / f"{kind}.json"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Catalogue '{kind}' not found")
    return json.loads(path.read_text(encoding="utf-8"))


@router.get(
    "/{kind}",
    response_model=list[ScenarioGroup],
    summary="Get attack-scenario catalogue",
)
async def get_scenarios(kind: CatalogueKind) -> list[dict]:
    """Return a scenario catalogue (``playground`` or ``agent``)."""
    return _load_catalogue(kind)
