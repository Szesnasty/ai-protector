"""Composite router for the Agent Wizard.

Collects all wizard sub-routers into a single mountable router.
main.py only needs:
    from src.wizard import wizard_router
    app.include_router(wizard_router, prefix="/v1")
"""

from fastapi import APIRouter

from src.wizard.routers.agents import router as agents_router
from src.wizard.routers.config import packs_router
from src.wizard.routers.config import router as config_router
from src.wizard.routers.integration import router as integration_router
from src.wizard.routers.rollout import router as rollout_router
from src.wizard.routers.tools_roles import router as tools_roles_router
from src.wizard.routers.traces import router as traces_router
from src.wizard.routers.validation import router as validation_router

wizard_router = APIRouter()
wizard_router.include_router(agents_router)
wizard_router.include_router(tools_roles_router)
wizard_router.include_router(config_router)
wizard_router.include_router(packs_router)
wizard_router.include_router(integration_router)
wizard_router.include_router(validation_router)
wizard_router.include_router(rollout_router)
wizard_router.include_router(traces_router)
