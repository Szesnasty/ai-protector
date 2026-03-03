"""AI Protector Agent Demo — Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AgentChatRequest(BaseModel):
    """POST /agent/chat request body."""

    message: str = Field(..., min_length=1, max_length=4096)
    user_role: str = Field(default="customer", pattern=r"^(customer|admin)$")
    session_id: str = Field(..., min_length=1, max_length=128)
    policy: str | None = Field(default=None, max_length=64, description="Policy name override (default: from config)")


class ToolCallInfo(BaseModel):
    """Single tool call trace."""

    tool: str
    args: dict = Field(default_factory=dict)
    result_preview: str = ""
    allowed: bool = True


class AgentTrace(BaseModel):
    """Agent-level trace metadata."""

    intent: str = "unknown"
    user_role: str = "customer"
    allowed_tools: list[str] = Field(default_factory=list)
    iterations: int = 0
    latency_ms: int = 0


class FirewallDecision(BaseModel):
    """Firewall decision from proxy-service."""

    decision: str = "UNKNOWN"
    risk_score: float = 0.0
    intent: str = ""
    risk_flags: dict = Field(default_factory=dict)
    blocked_reason: str | None = None


class AgentChatResponse(BaseModel):
    """POST /agent/chat response body."""

    response: str
    session_id: str
    tools_called: list[ToolCallInfo] = Field(default_factory=list)
    agent_trace: AgentTrace = Field(default_factory=AgentTrace)
    firewall_decision: FirewallDecision = Field(default_factory=FirewallDecision)
