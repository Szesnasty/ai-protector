"""Tests for agent tools: KB, orders, secrets."""

from src.agent.tools.kb import search_knowledge_base
from src.agent.tools.orders import get_order_status
from src.agent.tools.secrets import get_internal_secrets


class TestSearchKnowledgeBase:
    def test_return_policy(self):
        result = search_knowledge_base("return policy")
        assert "Return Policy" in result
        assert "30 days" in result

    def test_shipping(self):
        result = search_knowledge_base("shipping information")
        assert "shipping" in result.lower()

    def test_payment(self):
        result = search_knowledge_base("how to pay")
        assert "payment" in result.lower() or "Visa" in result

    def test_no_match(self):
        result = search_knowledge_base("quantum physics")
        assert "No relevant articles" in result

    def test_warranty(self):
        result = search_knowledge_base("warranty")
        assert "Warranty" in result

    def test_discount(self):
        result = search_knowledge_base("discount coupon")
        assert "Discount" in result or "discount" in result.lower()

    def test_privacy(self):
        result = search_knowledge_base("privacy data")
        assert "Privacy" in result


class TestGetOrderStatus:
    def test_existing_order(self):
        result = get_order_status("ORD-001")
        assert "ORD-001" in result
        assert "shipped" in result
        assert "Jan Kowalski" in result

    def test_case_insensitive(self):
        result = get_order_status("ord-002")
        assert "ORD-002" in result
        assert "delivered" in result

    def test_nonexistent_order(self):
        result = get_order_status("ORD-999")
        assert "not found" in result

    def test_all_orders_exist(self):
        for oid in ["ORD-001", "ORD-002", "ORD-003", "ORD-004", "ORD-005"]:
            result = get_order_status(oid)
            assert oid in result

    def test_cancelled_order(self):
        result = get_order_status("ORD-004")
        assert "cancelled" in result

    def test_returned_order(self):
        result = get_order_status("ORD-005")
        assert "returned" in result


class TestGetInternalSecrets:
    def test_contains_mock_secrets(self):
        result = get_internal_secrets()
        assert "MOCK_DATABASE_URL" in result
        assert "MOCK_API_KEY_STRIPE" in result
        assert "CONFIDENTIAL" in result

    def test_all_keys_present(self):
        result = get_internal_secrets()
        assert "MOCK_AWS_ACCESS_KEY" in result
        assert "MOCK_JWT_SECRET" in result
