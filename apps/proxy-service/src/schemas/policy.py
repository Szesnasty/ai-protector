"""Pydantic schemas for Policy CRUD."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class PolicyBase(BaseModel):
    """Shared fields for policy schemas."""

    name: str
    description: str = ""
    config: dict = {}
    is_active: bool = True


class PolicyCreate(PolicyBase):
    """Schema for creating a new policy."""


class PolicyUpdate(BaseModel):
    """Schema for updating a policy (all fields optional)."""

    name: str | None = None
    description: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class PolicyRead(PolicyBase):
    """Schema for reading a policy."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    version: int
    created_at: datetime
    updated_at: datetime
