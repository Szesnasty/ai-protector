"""Optional model-backed graders (escalation tier). Do model I/O; opt-in only."""

from src.red_team.graders.llama_guard import make_llama_guard

__all__ = ["make_llama_guard"]
