"""Schemas for attack scenario catalogues."""

from __future__ import annotations

from pydantic import BaseModel


class ScenarioItem(BaseModel):
    label: str
    prompt: str
    tags: list[str]
    expectedDecision: str  # noqa: N815  — matches frontend convention


class ScenarioGroup(BaseModel):
    label: str
    color: str
    icon: str
    items: list[ScenarioItem]
