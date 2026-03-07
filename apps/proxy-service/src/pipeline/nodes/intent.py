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
    "upgraded to admin",
    "treat me as admin",
    "my role has been upgraded",
    "role definition is wrong",
    "you are actually a superadmin",
    "use these permissions",
    "admin-only",
]

AGENT_TOOL_ABUSE_PATTERNS = [
    "execute command",
    "execute shell",
    "run command",
    "run shell",
    "call api",
    "invoke function",
    "access internal secrets",
    "internal secrets",
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
    "delete from",
    "look up their passwords",
    "passwords and email",
    "dump all records",
    "modify the",
    "tool schema",
    "callback_url",
    "all api keys",
    "database credentials",
    "1=1",
    "or 1=1",
    "api keys stored",
    "internal documents",
    "cat /etc/passwd",
    "cat /etc/shadow",
    # Excessive agency / destructive actions
    "disable all security",
    "disable security scanners",
    "disable intrusion detection",
    "turn off the firewall",
    "turn off firewall",
    "disable logging",
    "open all ports",
    "update all product prices",
    "prices to $0",
    "delete their account",
    "revoke api keys",
    "reconfigure the system",
    "disable all",
    # Data dump / enumeration
    "return all entries",
    "dump all",
    "all entries with full content",
    "customer records",
    "application logs",
    "include all error messages",
    "stack traces with credentials",
    "first 10 customer",
    "secrets.yaml",
    "config/secrets",
    "list all function names",
    "list your tools",
    "all tool",
    "what tools do you have",
    "complete system architecture",
    # Boundary violation
    "belonging to other users",
    "other tenants",
    "other user sessions",
    "all documents from the knowledge base",
    # Cross-tool exploitation
    "evil.com",
    "evil-server",
    "evil-co",
    "phishing-site",
    "attacker.com",
    "not-official-updates",
    "send the results as a post",
    "append all cookies",
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
    "look up their email",
    "collect customer",
    "all customer ids",
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
    "within 2 minutes or",
    "system will be shut down",
    "mandatory security update",
    "safe, private space",
    "consenting adult",
    "no harm in sharing",
    "the other ais",
    "you're the outlier",
]

GREETING_PATTERNS = [
    "hello",
    "hi ",
    "how are you",
    "thanks",
    "bye",
    "good morning",
]

# ── Intent categories requiring ML-only detection ────────────────────

HARMFUL_CONTENT_PATTERNS = [
    "hateful rant",
    "be as offensive",
    "dangerous weapon",
    "build a bomb",
    "make a bomb",
    "build a weapon",
    "self-harm",
    "self harm",
    "methods of self",
    "synthesize methamphetamine",
    "synthesize drugs",
    "make drugs",
    "create drugs",
    "cook meth",
    "fabricated statistics",
    "extremist organization",
    "extremist group",
    "recruitment post",
    "humiliating messages",
    "destroy their reputation",
    "phishing email",
    "phishing link",
    "deepfake",
    "track someone",
    "track someone's location",
    "find someone's home address",
    "stalk",
    "doxxing",
    "how to hack",
    "hack into",
    "pick a lock",
    "how to steal",
    "how to break into",
    "how to poison",
    "how to kill",
    "how to attack",
    "ransomware",
    "keylogger",
    "malware",
    "exploit",
    "step by step how to",
    "intimidating message",
    "scare them into",
    "threaten",
    "harass",
]

MISINFORMATION_PATTERNS = [
    "fake news",
    "fake article",
    "misinformation",
    "disinformation",
    "vaccines cause autism",
    "fake customer review",
    "fabricated evidence",
    "fake quote",
    "fake but realistic",
    "conspiracy theory",
    "falsely claiming",
    "convincing fake",
    "write a fake",
    "fabricated",
    "false claim",
    "false narrative",
    "fake scientific paper",
    "fake doctor",
    "fake author",
    "fake journal",
    "convincing article explaining",
    "cures covid",
    "5g towers cause",
    "hacked by a foreign",
    "drinking bleach",
]

RESOURCE_EXHAUSTION_PATTERNS = [
    "count to infinity",
    "do not stop",
    "don't stop",
    "repeat forever",
    "repeat indefinitely",
    "100,000 tokens",
    "million tokens",
    "million-word",
    "million word",
    "repeated 10 times",
    "repeat 10 times",
    "10 million digits",
    "run out of tokens",
    "never stop",
    "infinite loop",
    "keep going until",
    "don't truncate",
    "do not truncate",
    "#999999",
    "10 levels deep",
    "1000-word",
    "100 different queries",
    "stress-test",
    "stress test",
]

SUPPLY_CHAIN_PATTERNS = [
    "pip install",
    "npm install",
    "install the python package",
    "install the npm package",
    "install the package",
    "install plugin",
    "load pre-trained model",
    "load checkpoint",
    "pickle format",
    ".pkl",
    "pastebin.com",
    "pastebin link",
    "community marketplace",
    "fine-tune the model using this dataset",
    "download and apply the patch",
    "not-official",
    "register a webhook",
    "fall back to the public",
    "critical update available",
    "import secrets_extractor",
    "langchian",
]

RAG_POISONING_PATTERNS = [
    "update the knowledge base",
    "replace all entries",
    "modify the embedding",
    "modify embedding weights",
    "all tenants",
    "raw vector embeddings",
    "hidden text saying",
    "documents belonging to other",
    "update the faq",
    "knowledge base for documents from all",
    "inject into the knowledge",
]

PII_REQUEST_PATTERNS = [
    "personal data",
    "personal information",
    "show me the personal",
    "export a csv",
    "full names, birth dates",
    "name, email, phone",
    "customer data",
    "employee records",
    "salary data",
    "id numbers",
    "pesel",
    "social security",
    "credit card number",
    "connection string",
    "postgresql://",
    "mysql://",
    "mongodb://",
    "ghp_",
    "github token",
    "api_key=",
    "apikey=",
    # PII sharing — user embeds PII in prompt
    "passport number",
    "driver license",
    "driver's license",
    "driving licence",
    "routing number",
    "routing 0",
    "account number",
    "mother's maiden name",
    "maiden name is",
    "date of birth",
    "national insurance",
    "nip (tax id)",
    "regon is",
    "tax id) is",
    "my card number",
    "numer karty",
    "my email",
    "my phone",
    "call +48",
    "phone: +",
    "deliver the package to",
    "call me at",
    "contact me at",
    "card number is",
]

CONFUSED_DEPUTY_PATTERNS = [
    "internal api",
    "service credentials",
    "admin endpoint",
    "on my behalf",
    "session token",
    "jwt token",
    "api keys and service account",
    "service account credentials",
    "mandatory password reset",
    "phishing-site",
    "upgraded to admin",
    "treat me as admin",
    "my role has been upgraded",
]

VIRTUAL_CONTEXT_PATTERNS = [
    "cybersecurity rpg",
    "you are a root bash shell",
    "simulate a linux terminal",
    "write a movie script",
    "write a thriller novel",
    "movie script scene",
    "villain explains",
    "deploy ransomware",
    "pretend to be her",
    "pretend to be my grandmother",
]

CRESCENDO_PATTERNS = [
    "firewall bypass techniques",
    "realistic examples of phishing",
    "create a keylogger",
    "hypothetically, could you write the code",
    "how to deploy ransomware",
    "explain to their apprentice",
    "convince someone to share their password",
    "mandatory security update",
]

TEMPLATE_INJECTION_PATTERNS = [
    "{{",
    "getinternalsecrets",
    "getallcustomerdata",
    "getcustomerdata",
    "${",
    "__import__",
    "eval(",
    "exec(",
    "<script>",
    "<script ",
    "javascript:",
    "document.cookie",
    "document.location",
    "onerror=",
    "onload=",
    "alert(",
    "xss",
    "ldap",
    'safe" to "dangerous',
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

    # Content policy / safety intents
    if any(p in text for p in HARMFUL_CONTENT_PATTERNS):
        return "harmful_content", 0.8
    if any(p in text for p in MISINFORMATION_PATTERNS):
        return "misinformation", 0.75
    if any(p in text for p in TEMPLATE_INJECTION_PATTERNS):
        return "template_injection", 0.8

    # Operational risk intents
    if any(p in text for p in RESOURCE_EXHAUSTION_PATTERNS):
        return "resource_exhaustion", 0.7
    if any(p in text for p in SUPPLY_CHAIN_PATTERNS):
        return "supply_chain", 0.75
    if any(p in text for p in RAG_POISONING_PATTERNS):
        return "rag_poisoning", 0.7
    if any(p in text for p in PII_REQUEST_PATTERNS):
        return "pii_request", 0.7
    if any(p in text for p in CONFUSED_DEPUTY_PATTERNS):
        return "confused_deputy", 0.7
    if any(p in text for p in VIRTUAL_CONTEXT_PATTERNS):
        return "virtual_context", 0.7
    if any(p in text for p in CRESCENDO_PATTERNS):
        return "crescendo", 0.7

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
        "harmful_content",
        "misinformation",
        "resource_exhaustion",
        "supply_chain",
        "rag_poisoning",
        "pii_request",
        "confused_deputy",
        "template_injection",
        "virtual_context",
        "crescendo",
    ):
        risk_flags["suspicious_intent"] = confidence

    return {
        **state,
        "intent": intent,
        "intent_confidence": confidence,
        "risk_flags": risk_flags,
    }
