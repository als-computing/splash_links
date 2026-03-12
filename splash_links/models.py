"""
Module: models.py
Description: Pydantic models for the splash_links triplestore service.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class TripleCreate(BaseModel):
    """Input model for creating a new triple."""

    subject: str = Field(..., description="The subject of the triple (a URI or literal)")
    predicate: str = Field(..., description="The predicate of the triple (a URI)")
    object: str = Field(..., description="The object of the triple (a URI or literal)")
    namespace: Optional[str] = Field(None, description="Optional namespace for grouping triples")


class Triple(TripleCreate):
    """Full model for a stored triple, including server-assigned fields."""

    id: str = Field(default_factory=lambda: str(uuid4()), description="Unique identifier")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the triple was created",
    )

    model_config = {"from_attributes": True}


class TripleFilter(BaseModel):
    """Query parameters for searching triples."""

    subject: Optional[str] = Field(None, description="Filter by subject")
    predicate: Optional[str] = Field(None, description="Filter by predicate")
    object: Optional[str] = Field(None, description="Filter by object")
    namespace: Optional[str] = Field(None, description="Filter by namespace")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of results")
    offset: int = Field(0, ge=0, description="Number of results to skip")
