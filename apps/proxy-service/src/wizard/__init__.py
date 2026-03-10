"""Agent Wizard — self-contained module for agent onboarding.

This package owns all models, schemas, routers, services, and seeds
related to the Agent Wizard feature (specs 26-33).

Usage in main.py:
    from src.wizard import wizard_router, seed_wizard
    app.include_router(wizard_router, prefix="/v1")
    await seed_wizard()
"""

from src.wizard.router import wizard_router
from src.wizard.seed import seed_wizard

__all__ = ["wizard_router", "seed_wizard"]
