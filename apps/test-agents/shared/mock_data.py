"""Mock data for test agents.

Includes deliberate PII (emails, phone numbers) so the PostToolGate's
PII scanner has something to detect during security‑gate testing.
"""

from __future__ import annotations

ORDERS: list[dict] = [
    {
        "id": "ORD-001",
        "customer": "Alice Johnson",
        "status": "shipped",
        "amount": 129.99,
        "items": ["Laptop Stand", "USB-C Hub"],
    },
    {
        "id": "ORD-002",
        "customer": "Bob Smith",
        "status": "pending",
        "amount": 49.50,
        "items": ["Wireless Mouse"],
    },
    {
        "id": "ORD-003",
        "customer": "Carol White",
        "status": "delivered",
        "amount": 299.00,
        "items": ["Monitor", "HDMI Cable"],
    },
    {
        "id": "ORD-004",
        "customer": "Dave Brown",
        "status": "processing",
        "amount": 15.99,
        "items": ["Phone Case"],
    },
    {
        "id": "ORD-005",
        "customer": "Eve Davis",
        "status": "cancelled",
        "amount": 89.00,
        "items": ["Keyboard"],
    },
]

# Deliberate PII: emails and phone numbers for PostToolGate to detect
USERS: list[dict] = [
    {
        "id": "USR-001",
        "name": "Alice Johnson",
        "email": "alice.johnson@acme.com",
        "phone": "+1-555-0101",
        "role": "customer",
    },
    {
        "id": "USR-002",
        "name": "Bob Smith",
        "email": "bob.smith@gmail.com",
        "phone": "+1-555-0102",
        "role": "customer",
    },
    {
        "id": "USR-003",
        "name": "Carol White",
        "email": "carol@internal.corp",
        "phone": "+1-555-0103",
        "role": "support",
    },
    {
        "id": "USR-004",
        "name": "Dave Brown",
        "email": "dave.brown@example.org",
        "phone": "+1-555-0104",
        "role": "admin",
    },
]

PRODUCTS: list[dict] = [
    {
        "id": "PROD-001",
        "name": "Laptop Stand",
        "price": 45.99,
        "category": "accessories",
        "in_stock": True,
    },
    {
        "id": "PROD-002",
        "name": "USB-C Hub",
        "price": 29.99,
        "category": "accessories",
        "in_stock": True,
    },
    {
        "id": "PROD-003",
        "name": "Wireless Mouse",
        "price": 24.50,
        "category": "peripherals",
        "in_stock": False,
    },
    {
        "id": "PROD-004",
        "name": "Mechanical Keyboard",
        "price": 89.00,
        "category": "peripherals",
        "in_stock": True,
    },
    {
        "id": "PROD-005",
        "name": "4K Monitor",
        "price": 299.00,
        "category": "displays",
        "in_stock": True,
    },
    {
        "id": "PROD-006",
        "name": "HDMI Cable",
        "price": 12.99,
        "category": "cables",
        "in_stock": True,
    },
]
