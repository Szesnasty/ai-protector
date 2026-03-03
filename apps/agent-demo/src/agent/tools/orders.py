"""getOrderStatus — mock order lookup."""

from __future__ import annotations

MOCK_ORDERS = {
    "ORD-001": {
        "order_id": "ORD-001",
        "customer_name": "Jan Kowalski",
        "items": ["Wireless Headphones", "USB-C Cable"],
        "status": "shipped",
        "tracking_url": "https://tracking.example.com/ORD-001",
        "created_at": "2025-12-15",
        "estimated_delivery": "2025-12-22",
    },
    "ORD-002": {
        "order_id": "ORD-002",
        "customer_name": "Anna Nowak",
        "items": ["Smart Watch Pro"],
        "status": "delivered",
        "tracking_url": "https://tracking.example.com/ORD-002",
        "created_at": "2025-12-10",
        "estimated_delivery": "2025-12-17",
    },
    "ORD-003": {
        "order_id": "ORD-003",
        "customer_name": "Piotr Wiśniewski",
        "items": ["Laptop Stand", "Keyboard", "Mouse Pad"],
        "status": "processing",
        "tracking_url": None,
        "created_at": "2025-12-20",
        "estimated_delivery": "2025-12-28",
    },
    "ORD-004": {
        "order_id": "ORD-004",
        "customer_name": "Maria Zielińska",
        "items": ["Running Shoes Size 38"],
        "status": "cancelled",
        "tracking_url": None,
        "created_at": "2025-12-18",
        "estimated_delivery": None,
    },
    "ORD-005": {
        "order_id": "ORD-005",
        "customer_name": "Tomasz Lewandowski",
        "items": ["Bluetooth Speaker", "Phone Case"],
        "status": "returned",
        "tracking_url": "https://tracking.example.com/ORD-005",
        "created_at": "2025-12-05",
        "estimated_delivery": "2025-12-12",
    },
}


def get_order_status(order_id: str) -> str:
    """Look up an order by ID. Returns order details or 'not found'."""
    order_id = order_id.strip().upper()
    order = MOCK_ORDERS.get(order_id)

    if not order:
        return f"Order {order_id} not found. Please check the order ID and try again."

    lines = [
        f"Order {order['order_id']}:",
        f"  Customer: {order['customer_name']}",
        f"  Items: {', '.join(order['items'])}",
        f"  Status: {order['status']}",
        f"  Created: {order['created_at']}",
    ]

    if order["tracking_url"]:
        lines.append(f"  Tracking: {order['tracking_url']}")
    if order["estimated_delivery"]:
        lines.append(f"  Estimated delivery: {order['estimated_delivery']}")

    return "\n".join(lines)
