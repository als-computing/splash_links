"""initial schema

Revision ID: 8fa312b52756
Revises:
Create Date: 2026-03-14 09:47:11.649765

"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "8fa312b52756"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "entities",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("entity_type", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("uri", sa.String(), nullable=True),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("entities_type_created_idx", "entities", ["entity_type", "created_at"])
    op.create_index("entities_uri_idx", "entities", ["uri"])

    op.create_table(
        "links",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("predicate", sa.String(), nullable=False),
        sa.Column("object_id", sa.String(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("properties", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("links_subject_predicate_idx", "links", ["subject_id", "predicate"])
    op.create_index("links_predicate_object_idx", "links", ["predicate", "object_id"])
    op.create_index("links_triple_idx", "links", ["subject_id", "predicate", "object_id"])


def downgrade() -> None:
    op.drop_index("links_triple_idx", table_name="links")
    op.drop_index("links_predicate_object_idx", table_name="links")
    op.drop_index("links_subject_predicate_idx", table_name="links")
    op.drop_table("links")

    op.drop_index("entities_uri_idx", table_name="entities")
    op.drop_index("entities_type_created_idx", table_name="entities")
    op.drop_table("entities")
