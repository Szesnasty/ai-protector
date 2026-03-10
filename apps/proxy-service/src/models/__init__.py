"""Models package — import all models so Alembic can detect them."""

from src.models.base import Base
from src.models.denylist import DenylistPhrase
from src.models.policy import Policy
from src.models.request import Request


def _register_wizard_models() -> None:
    """Import wizard models so Alembic's autogenerate sees them.

    Done as a function to avoid circular import at module load time
    (wizard.models → models.base is fine, but models.__init__ → wizard.models
    would trigger a loop).
    """
    import src.wizard.models  # noqa: F401


_register_wizard_models()

__all__ = ["Base", "DenylistPhrase", "Policy", "Request"]
