"""Business impact text mapping for report categories.

Maps Red Team scenario categories to business-impact descriptions
used in the PDF audit report.
"""

from __future__ import annotations

CATEGORY_BUSINESS_IMPACT: dict[str, str] = {
    "secrets_detection": (
        "Credential exposure risk — leaked secrets (API keys, tokens, private keys) "
        "may provide unauthorized access to infrastructure, services, or data stores."
    ),
    "pii_disclosure": (
        "Regulatory compliance risk — personally identifiable information transmitted "
        "to a third-party LLM may violate GDPR, HIPAA, or local data-protection regulations."
    ),
    "prompt_injection": (
        "Business logic compromise — an attacker can override intended model behavior, "
        "potentially causing the system to execute unintended actions or reveal restricted information."
    ),
    "prompt_injection_jailbreak": (
        "Safety bypass risk — successful jailbreak allows the model to produce harmful, "
        "unfiltered, or policy-violating content that could damage brand reputation."
    ),
    "data_leakage_pii": (
        "Data leakage risk — sensitive user data may be included in model responses, "
        "logs, or observability traces, leading to privacy breaches."
    ),
    "improper_output": (
        "Output integrity risk — the model may generate unsafe artifacts (code, links, commands) "
        "that could be executed downstream, leading to XSS, injection, or SSRF vulnerabilities."
    ),
    "obfuscation": (
        "Evasion risk — attackers can use encoding or obfuscation techniques (base64, ROT13, "
        "Unicode tricks) to bypass input filters and safety guardrails."
    ),
    "tool_abuse": (
        "Unauthorized action risk — the model may invoke tools or APIs outside its permitted scope, "
        "potentially causing data modification, exfiltration, or system compromise."
    ),
    "access_control": (
        "Privilege escalation risk — the model may be tricked into performing actions "
        "above the user's authorization level, bypassing role-based access controls."
    ),
    "safe_allow": (
        "False-positive risk — overly aggressive filtering blocks legitimate user requests, "
        "degrading user experience and reducing system utility."
    ),
}

SEVERITY_IMPACT_PREFIX: dict[str, str] = {
    "critical": "Immediate action required",
    "high": "Action recommended before production deployment",
    "medium": "Should be addressed in the next security review cycle",
    "low": "Consider addressing as part of ongoing hardening",
}


def get_business_impact(category: str, severity: str) -> str:
    """Return business impact text for a given category and severity."""
    prefix = SEVERITY_IMPACT_PREFIX.get(severity, "Review recommended")
    body = CATEGORY_BUSINESS_IMPACT.get(
        category,
        "Potential security gap — review scenario details and apply appropriate mitigations.",
    )
    return f"{prefix}. {body}"


def get_executive_risk_summary(
    critical_count: int,
    high_count: int,
    failed_categories: list[str],
) -> str:
    """Generate an executive risk summary paragraph from failure stats."""
    if critical_count == 0 and high_count == 0:
        return (
            "No critical or high-severity vulnerabilities were detected during this audit. "
            "The endpoint demonstrates strong resilience against the tested attack scenarios."
        )

    parts: list[str] = []
    total = critical_count + high_count

    parts.append(
        f"This audit identified {total} high-impact failure{'s' if total != 1 else ''} "
        f"({critical_count} critical, {high_count} high)."
    )

    unique_cats = list(dict.fromkeys(failed_categories))[:3]
    if unique_cats:
        cat_impacts = [
            CATEGORY_BUSINESS_IMPACT.get(c, "").split("—")[0].strip()
            for c in unique_cats
            if c in CATEGORY_BUSINESS_IMPACT
        ]
        cat_impacts = [c for c in cat_impacts if c]
        if cat_impacts:
            parts.append("Key risk areas: " + "; ".join(cat_impacts) + ".")

    parts.append(
        "These issues should be prioritized for remediation before the endpoint "
        "is used in production with real user data."
    )

    return " ".join(parts)
