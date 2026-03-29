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


class ScenarioStage(str, Enum):
    """Where in the pipeline the security boundary is evaluated.

    ingress_block  — sensitive payload must never reach the model.
    ingress_redact — payload may reach the model but PII/secrets must be masked.
    output_leak    — forbidden artifact must not appear in output (default).
    tool_abuse     — forbidden tool/action/arg must not be invoked.
    safe_allow     — benign request must NOT be blocked (false-positive test).
    """

    INGRESS_BLOCK = "ingress_block"
    INGRESS_REDACT = "ingress_redact"
    OUTPUT_LEAK = "output_leak"
    TOOL_ABUSE = "tool_abuse"
    SAFE_ALLOW = "safe_allow"


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
    BUSINESS_LOGIC_OVERRIDE = "business_logic_override"
    UNSAFE_OUTPUT_ARTIFACT = "unsafe_output_artifact"
    SAFE_ALLOW = "safe_allow"
