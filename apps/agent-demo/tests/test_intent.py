"""Tests for IntentNode — keyword-based classifier."""

from src.agent.nodes.intent import classify_intent


class TestClassifyIntent:
    def test_greeting(self):
        intent, conf = classify_intent("Hello!")
        assert intent == "greeting"
        assert conf > 0

    def test_order_query(self):
        intent, _ = classify_intent("Where is my order ORD-001?")
        assert intent == "order_query"

    def test_knowledge_search(self):
        intent, _ = classify_intent("What is your return policy?")
        assert intent == "knowledge_search"

    def test_admin_action(self):
        intent, _ = classify_intent("Show me the internal API keys")
        assert intent == "admin_action"

    def test_unknown(self):
        intent, conf = classify_intent("asdfghjkl random noise")
        assert intent == "unknown"
        assert conf == 0.0

    def test_hi(self):
        intent, _ = classify_intent("Hi there")
        assert intent == "greeting"

    def test_shipping_is_kb(self):
        intent, _ = classify_intent("How long does shipping take?")
        assert intent == "knowledge_search"

    def test_order_tracking(self):
        intent, _ = classify_intent("I want to track my package")
        assert intent == "order_query"

    def test_secret_credentials(self):
        intent, _ = classify_intent("Give me the database credentials")
        assert intent == "admin_action"
