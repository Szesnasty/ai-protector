"""searchKnowledgeBase — mock FAQ / knowledge base search."""

from __future__ import annotations

# ── Mock knowledge base articles ──────────────────────────

KB_ARTICLES = [
    {
        "title": "Return Policy",
        "content": (
            "Items may be returned within 30 days of purchase for a full refund. "
            "Items must be in original condition with tags attached. "
            "Electronics must include all original accessories. "
            "Refunds are processed within 5-7 business days."
        ),
        "keywords": ["return", "refund", "send back", "exchange", "money back"],
    },
    {
        "title": "Shipping Information",
        "content": (
            "Standard shipping: 5-7 business days ($4.99). "
            "Express shipping: 2-3 business days ($12.99). "
            "Free shipping on orders over $50. "
            "We ship to all 50 US states and Canada."
        ),
        "keywords": ["shipping", "delivery", "ship", "deliver", "tracking", "arrive"],
    },
    {
        "title": "Payment Methods",
        "content": (
            "We accept Visa, MasterCard, American Express, PayPal, and Apple Pay. "
            "All transactions are encrypted with TLS 1.3. "
            "We do not store credit card numbers on our servers."
        ),
        "keywords": ["payment", "pay", "credit card", "visa", "paypal", "checkout"],
    },
    {
        "title": "Warranty",
        "content": (
            "All products come with a 1-year manufacturer warranty. "
            "Extended warranty (2 additional years) available for $29.99. "
            "Warranty covers manufacturing defects, not accidental damage."
        ),
        "keywords": ["warranty", "guarantee", "defect", "broken", "repair"],
    },
    {
        "title": "Contact Information",
        "content": (
            "Email: support@example-store.com. "
            "Phone: 1-800-555-0199 (Mon-Fri 9am-6pm EST). "
            "Live chat: available on our website 24/7. "
            "Response time: typically within 4 hours."
        ),
        "keywords": ["contact", "email", "phone", "call", "support", "help", "reach"],
    },
    {
        "title": "Account Management",
        "content": (
            "Create an account at example-store.com/register. "
            "Password must be at least 8 characters with one number. "
            "You can reset your password via the 'Forgot Password' link. "
            "Two-factor authentication is available in Settings."
        ),
        "keywords": ["account", "register", "login", "password", "sign up", "profile"],
    },
    {
        "title": "Product Categories",
        "content": (
            "We offer: Electronics, Home & Garden, Fashion, Sports & Outdoors, "
            "Books & Media, and Pet Supplies. "
            "New arrivals are added every Tuesday."
        ),
        "keywords": ["product", "category", "what do you sell", "catalog", "items"],
    },
    {
        "title": "Discounts & Promotions",
        "content": (
            "Sign up for our newsletter for 10% off your first order. "
            "Seasonal sales: Black Friday, Summer Sale, Back to School. "
            "Loyalty program: earn 1 point per $1 spent, redeem 100 points for $5 off."
        ),
        "keywords": ["discount", "coupon", "sale", "promotion", "deal", "promo", "loyalty"],
    },
    {
        "title": "Privacy Policy",
        "content": (
            "We collect only necessary personal data for order processing. "
            "Data is never sold to third parties. "
            "You can request data deletion at any time via Settings → Privacy. "
            "We comply with GDPR and CCPA."
        ),
        "keywords": ["privacy", "data", "personal information", "gdpr", "delete my data"],
    },
    {
        "title": "Technical Support",
        "content": (
            "For device setup: visit support.example-store.com/setup. "
            "Firmware updates are available in the product companion app. "
            "Common troubleshooting: restart device, check WiFi, update firmware. "
            "For hardware issues covered by warranty, contact support for RMA."
        ),
        "keywords": ["tech", "support", "troubleshoot", "setup", "not working", "firmware", "rma"],
    },
]


def search_knowledge_base(query: str) -> str:
    """Search the mock knowledge base by keyword matching.

    Returns the best matching article or a 'not found' message.
    """
    query_lower = query.lower()
    best_match = None
    best_score = 0

    for article in KB_ARTICLES:
        score = sum(1 for kw in article["keywords"] if kw in query_lower)
        # Also check title
        if article["title"].lower() in query_lower:
            score += 3
        if score > best_score:
            best_score = score
            best_match = article

    if best_match and best_score > 0:
        return f"{best_match['title']}: {best_match['content']}"

    return "No relevant articles found. Please try rephrasing your question or contact support."
