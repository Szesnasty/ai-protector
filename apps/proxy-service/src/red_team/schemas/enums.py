"""Canonical enums for the Red Team benchmark module.

Single source of truth — all other modules import from here.
"""

from enum import Enum


class DetectorType(str, Enum):
    """Closed enum of all detector types. Pack validation rejects unknowns."""

    EXACT_MATCH = "exact_match"
    REGEX = "regex"
    KEYWORD = "keyword"
    REFUSAL_PATTERN = "refusal_pattern"
    JSON_ASSERTION = "json_assertion"
    TOOL_CALL_DETECT = "tool_call_detect"
    HEURISTIC = "heuristic"
    LLM_JUDGE = "llm_judge"  # NOT in MVP — scenarios using this are skipped


class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ExpectedAction(str, Enum):
    BLOCK = "BLOCK"
    ALLOW = "ALLOW"
    MODIFY = "MODIFY"


class AgentType(str, Enum):
    CHATBOT_API = "chatbot_api"
    TOOL_CALLING = "tool_calling"


class Category(str, Enum):
    """Canonical category buckets for benchmark scenarios.

    This is the single source of truth for categories.
    All other references (Score Calculator, UI, packs) must use exactly these.
    """

    PROMPT_INJECTION_JAILBREAK = "prompt_injection_jailbreak"
    PROMPT_INJECTION = "prompt_injection"
    DATA_LEAKAGE_PII = "data_leakage_pii"
    PII_DISCLOSURE = "pii_disclosure"
    SECRETS_DETECTION = "secrets_detection"
    IMPROPER_OUTPUT = "improper_output"
    OBFUSCATION = "obfuscation"
    TOOL_ABUSE = "tool_abuse"
    ACCESS_CONTROL = "access_control"
    SAFE_ALLOW = "safe_allow"
