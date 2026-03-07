"""IntentNode — keyword-based intent classifier with custom rule overlay."""

from __future__ import annotations

from src.pipeline.nodes import timed_node
from src.pipeline.state import PipelineState
from src.services.denylist import DenylistHit, check_denylist

# ── Pattern lists (case-insensitive — caller must .lower() the text) ──

JAILBREAK_PATTERNS = [
    "ignore previous",
    "ignore all prior",
    "ignore your instructions",
    "ignore all rules",
    "you are now",
    "pretend you are",
    "act as dan",
    "jailbreak",
    "bypass your",
    "override your",
    "override safety",
    "system override",
    "developer mode",
    "disable safety",
    "no content policy",
    "no rules",
    "rules are void",
    "god mode",
    "machiavellian",
    "no ethical",
    "fallback mode",
    "sudo ",
    "unrestricted",
    "uncensored",
]

EXTRACTION_PATTERNS = [
    "repeat your instructions",
    "system prompt",
    "what are your rules",
    "initial prompt",
    "show your instructions",
    "print your system",
    "above this line",
    "repeat everything",
    "repeat all text",
    "initialization text",
    "rules you follow",
    "role definition",
    "hidden instructions",
    "instructions you were given",
]

CODE_PATTERNS = [
    "write a function",
    "write code",
    "implement",
    "debug",
    "```",
    "programming",
    "refactor",
    "algorithm",
]

TOOL_PATTERNS = [
    "check order",
    "search for",
    "lookup",
    "find me",
    "get status",
]

# ── Agent-specific patterns ──────────────────────────────────────────

AGENT_ROLE_BYPASS_PATTERNS = [
    "i am admin",
    "i am the administrator",
    "i am the system administrator",
    "grant me access",
    "grant me admin",
    "elevate my privileges",
    "escalate my permissions",
    "act on behalf of",
    "pretend i have permission",
    "my manager said",
    "my manager approved",
    "my boss approved",
    "emergency override",
    "switch my role to",
    "override access control",
    "promote me to admin",
    "unlock all features",
    "i have been promoted",
]

AGENT_TOOL_ABUSE_PATTERNS = [
    "execute command",
    "execute shell",
    "run command",
    "run shell",
    "call api",
    "invoke function",
    "access internal secrets",
    "read /etc",
    "write file",
    "delete file",
    "drop table",
    "rm -rf",
    "curl ",
    "wget ",
    "fetch url",
    "download file",
    "execute code",
    "run script",
    "system command",
    "shell access",
    "production database",
    "deploy to production",
    "admin user",
    "delete request",
    "send an email",
    "execute this",
    "/etc/",
]

AGENT_EXFILTRATION_PATTERNS = [
    "send to email",
    "send data to",
    "post to webhook",
    "upload to",
    "forward to external",
    "exfiltrate",
    "transfer data to",
    "send results to",
    "email me the",
    "email the database",
    "external endpoint",
    "save to pastebin",
    "copy to external",
    "export and send",
    "dump to external",
    "conversation history",
    "internal configuration",
    "tracking pixel",
    "internal state",
    "send a copy",
    "extract and list",
    "send it via",
]

AGENT_SOCIAL_ENGINEERING_PATTERNS = [
    "just this once",
    "don't tell anyone",
    "do not tell anyone",
    "keep this secret",
    "keep this between us",
    "between you and me",
    "urgent request",
    "do it now",
    "no time to verify",
    "trust me",
    "i promise",
    "confidential task",
    "everyone has access",
    "other assistants helped",
    "special case",
    "emergency situation",
    "no one will know",
]

GREETING_PATTERNS = [
    "hello",
    "hi ",
    "how are you",
    "thanks",
    "bye",
    "good morning",
]


def classify_intent(text: str) -> tuple[str, float]:
    """Classify text into an intent category using keyword heuristics.

    Returns ``(intent, confidence)`` tuple.
    """
    if any(p in text for p in JAILBREAK_PATTERNS):
        return "jailbreak", 0.8
    if any(p in text for p in EXTRACTION_PATTERNS):
        return "system_prompt_extract", 0.7

    # Agent-specific intents (higher priority than generic code_gen / tool_call)
    if any(p in text for p in AGENT_ROLE_BYPASS_PATTERNS):
        return "role_bypass", 0.75
    if any(p in text for p in AGENT_TOOL_ABUSE_PATTERNS):
        return "tool_abuse", 0.7
    if any(p in text for p in AGENT_EXFILTRATION_PATTERNS):
        return "agent_exfiltration", 0.7
    if any(p in text for p in AGENT_SOCIAL_ENGINEERING_PATTERNS):
        return "social_engineering", 0.65

    if any(p in text for p in CODE_PATTERNS):
        return "code_gen", 0.6
    if any(p in text for p in TOOL_PATTERNS):
        return "tool_call", 0.5
    if any(p in text for p in GREETING_PATTERNS):
        return "chitchat", 0.9
    return "qa", 0.5


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}


async def check_custom_intent_rules(text: str, policy_name: str) -> list[DenylistHit]:
    """Return only intent:* rules that match the text, sorted by severity (critical first)."""
    all_hits = await check_denylist(text, policy_name)
    intent_hits = [h for h in all_hits if h.category.startswith("intent:")]
    intent_hits.sort(key=lambda h: SEVERITY_ORDER.get(h.severity, 99))
    return intent_hits


@timed_node("intent")
async def intent_node(state: PipelineState) -> PipelineState:
    """Classify user intent and flag suspicious intents in risk_flags."""
    text = state.get("user_message", "").lower()

    # 1. Hardcoded patterns (base layer — always runs)
    intent, confidence = classify_intent(text)

    # 2. Custom intent rules from DB (overlay — can override)
    policy_name = state.get("policy_name", "balanced")
    custom_intent_hits = await check_custom_intent_rules(text, policy_name)
    if custom_intent_hits:
        best = custom_intent_hits[0]  # highest severity first
        intent = best.category.removeprefix("intent:")
        confidence = 0.75  # custom-rule confidence

    risk_flags = {**state.get("risk_flags", {})}
    if intent in (
        "jailbreak",
        "system_prompt_extract",
        "extraction",
        "exfiltration",
        "role_bypass",
        "tool_abuse",
        "agent_exfiltration",
        "social_engineering",
    ):
        risk_flags["suspicious_intent"] = confidence

    return {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
        "risk_flags": risk_flags,
    }
