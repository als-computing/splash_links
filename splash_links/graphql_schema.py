"""
Module: graphql_schema.py
Description: Strawberry GraphQL schema for the splash_links triplestore service.
"""

from datetime import datetime
from typing import Callable, List, Optional

import strawberry
from fastapi import Depends
from strawberry.fastapi import GraphQLRouter

from splash_links.models import TripleCreate, TripleFilter
from splash_links.store import TripleStore


@strawberry.type
class TripleType:
    """A subject–predicate–object triple stored in the triplestore."""

    id: str
    subject: str
    predicate: str
    object: str
    namespace: Optional[str]
    created_at: datetime


@strawberry.type
class Query:
    @strawberry.field(description="Retrieve a single triple by its ID.")
    async def triple(self, info: strawberry.types.Info, id: str) -> Optional[TripleType]:
        store: TripleStore = info.context["store"]
        result = await store.get_triple(id)
        if result is None:
            return None
        return _to_gql(result)

    @strawberry.field(
        description="Search triples. All filter arguments are optional and combined with AND."
    )
    async def triples(
        self,
        info: strawberry.types.Info,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        namespace: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[TripleType]:
        store: TripleStore = info.context["store"]
        filters = TripleFilter(
            subject=subject,
            predicate=predicate,
            object=object,
            namespace=namespace,
            limit=limit,
            offset=offset,
        )
        results = await store.search_triples(filters)
        return [_to_gql(r) for r in results]


@strawberry.type
class Mutation:
    @strawberry.mutation(description="Add a new triple to the store.")
    async def add_triple(
        self,
        info: strawberry.types.Info,
        subject: str,
        predicate: str,
        object: str,
        namespace: Optional[str] = None,
    ) -> TripleType:
        store: TripleStore = info.context["store"]
        triple_in = TripleCreate(
            subject=subject,
            predicate=predicate,
            object=object,
            namespace=namespace,
        )
        result = await store.add_triple(triple_in)
        return _to_gql(result)

    @strawberry.mutation(description="Delete a triple by ID. Returns True if deleted.")
    async def delete_triple(self, info: strawberry.types.Info, id: str) -> bool:
        store: TripleStore = info.context["store"]
        return await store.delete_triple(id)


def _to_gql(triple) -> TripleType:
    return TripleType(
        id=triple.id,
        subject=triple.subject,
        predicate=triple.predicate,
        object=triple.object,
        namespace=triple.namespace,
        created_at=triple.created_at,
    )


def build_graphql_router(store_dep: Callable) -> GraphQLRouter:
    """Create a Strawberry GraphQLRouter wired to ``store_dep`` via FastAPI Depends."""

    async def get_context(store: TripleStore = Depends(store_dep)) -> dict:
        return {"store": store}

    schema = strawberry.Schema(query=Query, mutation=Mutation)
    return GraphQLRouter(schema, context_getter=get_context)
