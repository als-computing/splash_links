"""
Module: store.py
Description: Abstract base class defining the interface for triple storage backends.
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from splash_links.models import Triple, TripleCreate, TripleFilter


class TripleStore(ABC):
    """Abstract base class for triplestore backends."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the store (create tables, indexes, etc.)."""
        ...

    @abstractmethod
    async def add_triple(self, triple_in: TripleCreate) -> Triple:
        """Persist a new triple and return it with server-assigned fields."""
        ...

    @abstractmethod
    async def get_triple(self, triple_id: str) -> Optional[Triple]:
        """Retrieve a single triple by its ID, or None if not found."""
        ...

    @abstractmethod
    async def search_triples(self, filters: TripleFilter) -> List[Triple]:
        """Search for triples matching the given filter criteria."""
        ...

    @abstractmethod
    async def delete_triple(self, triple_id: str) -> bool:
        """Delete a triple by ID. Returns True if deleted, False if not found."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Clean up any resources (connections, file handles, etc.)."""
        ...
