"""Composite router for the Agent Wizard.

Collects all wizard sub-routers into a single mountable router.
main.py only needs:
    from src.wizard import wizard_router
    app.include_router(wizard_router, prefix="/v1")
"""

from fastapi import APIRouter

from src.wizard.routers.agents import router as agents_router

wizard_router = APIRouter()
wizard_router.include_router(agents_router)
