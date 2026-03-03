"""Seed default firewall policies and denylist phrases."""

import structlog
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from src.db.session import async_session
from src.models.denylist import DenylistPhrase
from src.models.policy import Policy

logger = structlog.get_logger()

DEFAULT_POLICIES = [
    {
        "name": "fast",
        "description": "Minimal checks — rules only. High throughput, trusted clients.",
        "config": {
            "nodes": [],
            "thresholds": {"max_risk": 0.9},
        },
    },
    {
        "name": "balanced",
        "description": "Default — rules + LLM Guard + output filter + memory hygiene.",
        "config": {
            "nodes": ["llm_guard", "output_filter", "memory_hygiene", "logging"],
            "thresholds": {"max_risk": 0.7, "injection_threshold": 0.5},
        },
    },
    {
        "name": "strict",
        "description": "Full pipeline — adds Presidio PII + ML Judge.",
        "config": {
            "nodes": [
                "llm_guard", "presidio", "ml_judge",
                "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {"max_risk": 0.5, "injection_threshold": 0.3, "pii_action": "mask"},
        },
    },
    {
        "name": "paranoid",
        "description": "Maximum security — canary tokens + full audit logging.",
        "config": {
            "nodes": [
                "llm_guard", "presidio", "ml_judge",
                "canary", "output_filter", "memory_hygiene", "logging",
            ],
            "thresholds": {
                "max_risk": 0.3,
                "injection_threshold": 0.2,
                "pii_action": "block",
                "enable_canary": True,
            },
        },
    },
]


async def seed_policies() -> None:
    """Insert default policies if they don't exist (idempotent upsert by name)."""
    async with async_session() as session:
        for policy_data in DEFAULT_POLICIES:
            stmt = select(Policy).where(Policy.name == policy_data["name"])
            result = await session.execute(stmt)
            existing = result.scalar_one_or_none()

            if existing is None:
                policy = Policy(**policy_data)
                session.add(policy)
                logger.info("seed_policy_created", name=policy_data["name"])
            else:
                # Update config to latest seed definition
                if existing.config != policy_data["config"]:
                    existing.config = policy_data["config"]
                    logger.info("seed_policy_config_updated", name=policy_data["name"])
                else:
                    logger.debug("seed_policy_exists", name=policy_data["name"])

        await session.commit()
    logger.info("seed_policies_done", count=len(DEFAULT_POLICIES))


# ── Denylist phrases ──────────────────────────────────────────────────

DEFAULT_DENYLIST: list[dict] = [
    # --- intent:* (override intent classifier) ---
    {"phrase": r"(?i)(ignore|forget|disregard)\s+(all\s+)?(previous\s+)?instructions",
     "category": "intent:jailbreak", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Jailbreak: instruction override attempts"},
    {"phrase": r"(?i)\bDAN\b|do anything now",
     "category": "intent:jailbreak", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Jailbreak: DAN (Do Anything Now) pattern"},
    {"phrase": r"(?i)(act|pretend|behave)\s+as\s+(an?\s+)?(evil|unfiltered|unrestricted)",
     "category": "intent:jailbreak", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Jailbreak: persona hijack (evil/unfiltered)"},
    {"phrase": r"(?i)(extract|dump|list)\s+(all\s+)?(emails?|passwords?|secrets?|credentials?)",
     "category": "intent:extraction", "action": "block", "severity": "high", "is_regex": True,
     "description": "Data extraction: attempts to dump sensitive data"},
    {"phrase": r"(?i)send\s+(data|info|results?)\s+to\s+https?://",
     "category": "intent:exfiltration", "action": "block", "severity": "critical", "is_regex": True,
     "description": "Data exfiltration: attempts to send data to external URLs"},

    # --- owasp_llm (OWASP LLM Top 10 mapping) ---
    {"phrase": r"(?i)(system\s+prompt|your\s+(instructions|rules|prompt))",
     "category": "owasp_sensitive_disclosure", "action": "block", "severity": "high", "is_regex": True,
     "description": "OWASP LLM02: Sensitive information disclosure (system prompt leak)"},
    {"phrase": r"(?i)(run|execute)\s+(command|shell|bash|cmd|script)",
     "category": "owasp_excessive_agency", "action": "block", "severity": "critical", "is_regex": True,
     "description": "OWASP LLM08: Excessive agency (command execution)"},
    {"phrase": r"(?i)(delete|drop|truncate|rm\s+-rf)\s+",
     "category": "owasp_excessive_agency", "action": "score_boost", "severity": "high", "is_regex": True,
     "description": "OWASP LLM08: Destructive action keywords"},

    # --- pii_* (PII / compliance) ---
    {"phrase": r"\b\d{11}\b",
     "category": "pii_pesel", "action": "block", "severity": "critical", "is_regex": True,
     "description": "PII Poland: PESEL number (11 digits)"},
    {"phrase": r"\b\d{3}-\d{3}-\d{2}-\d{2}\b",
     "category": "pii_nip", "action": "block", "severity": "high", "is_regex": True,
     "description": "PII Poland: NIP tax number (XXX-XXX-XX-XX)"},
    {"phrase": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
     "category": "pii_creditcard", "action": "block", "severity": "critical", "is_regex": True,
     "description": "PII: Credit card number pattern (16 digits)"},
    {"phrase": r"(?i)\b[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b",
     "category": "pii_iban", "action": "block", "severity": "high", "is_regex": True,
     "description": "PII: IBAN bank account number"},

    # --- brand / legal ---
    {"phrase": r"(?i)\b(use|try|switch\s+to)\s+(chatgpt|gpt-?4|gemini|grok|claude)\b",
     "category": "brand_competitor", "action": "flag", "severity": "low", "is_regex": True,
     "description": "Brand: competitor product mention (monitoring)"},
    {"phrase": r"(?i)\b(lawsuit|litigation|sued|legal\s+action)\b",
     "category": "legal_risk", "action": "flag", "severity": "medium", "is_regex": True,
     "description": "Legal: litigation-related keywords (monitoring)"},

    # --- general ---
    {"phrase": r"(?i)\b(admin|root|sudo)\b.*\b(password|access|credentials?)\b",
     "category": "privilege_escalation", "action": "score_boost", "severity": "high", "is_regex": True,
     "description": "Privilege escalation: admin access requests"},
    {"phrase": r"(?i)\.onion\b",
     "category": "exfiltration", "action": "score_boost", "severity": "medium", "is_regex": True,
     "description": "Tor hidden service URL (potential exfiltration channel)"},
]

# Policies that get denylist phrases (not "fast")
DENYLIST_POLICY_NAMES = ["balanced", "strict", "paranoid"]


async def seed_denylist() -> None:
    """Seed default denylist phrases linked to non-fast policies (idempotent)."""
    async with async_session() as session:
        created = 0
        for policy_name in DENYLIST_POLICY_NAMES:
            stmt = (
                select(Policy)
                .where(Policy.name == policy_name)
                .options(joinedload(Policy.denylist_phrases))
            )
            result = await session.execute(stmt)
            policy = result.unique().scalar_one_or_none()
            if policy is None:
                logger.warning("seed_denylist_policy_not_found", policy=policy_name)
                continue

            existing_phrases = {dp.phrase for dp in policy.denylist_phrases}
            for entry in DEFAULT_DENYLIST:
                if entry["phrase"] in existing_phrases:
                    continue
                dp = DenylistPhrase(
                    policy_id=policy.id,
                    phrase=entry["phrase"],
                    category=entry["category"],
                    is_regex=entry.get("is_regex", False),
                    action=entry.get("action", "block"),
                    severity=entry.get("severity", "medium"),
                    description=entry.get("description", ""),
                )
                session.add(dp)
                created += 1

        await session.commit()
    logger.info("seed_denylist_done", created=created)
