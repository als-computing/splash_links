"""add embeddings table

Revision ID: 6a86ce49c068
Revises: 8fa312b52756
Create Date: 2026-04-05 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.types import UserDefinedType

from alembic import op


class PostgreSQLVectorType(UserDefinedType):
    cache_ok = True

    def get_col_spec(self, **_kw) -> str:
        return "vector"

# revision identifiers, used by Alembic.
revision: str = "6a86ce49c068"
down_revision: Union[str, Sequence[str], None] = "8fa312b52756"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    vector_type: sa.types.TypeEngine
    if bind.dialect.name == "postgresql":
        vector_type = PostgreSQLVectorType()
    else:
        vector_type = sa.LargeBinary()

    op.create_table(
        "embeddings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entity_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("embedding_model", sa.String(), nullable=False),
        sa.Column("vector", vector_type, nullable=False),
        sa.Column("dimensions", sa.Integer(), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "embeddings_entity_model_created_idx",
        "embeddings",
        ["entity_id", "embedding_model", "created_at"],
    )
    op.create_index(
        "embeddings_model_dimensions_idx",
        "embeddings",
        ["embedding_model", "dimensions"],
    )


def downgrade() -> None:
    op.drop_index("embeddings_model_dimensions_idx", table_name="embeddings")
    op.drop_index("embeddings_entity_model_created_idx", table_name="embeddings")
    op.drop_table("embeddings")