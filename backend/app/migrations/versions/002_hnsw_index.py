"""Replace IVFFlat with HNSW index for better vector search recall at scale.

IVFFlat is fast to build but recall degrades as the corpus grows past a few
hundred-thousand rows and requires periodic ``REINDEX`` after large inserts
to keep cluster boundaries balanced. HNSW (hierarchical navigable small
world) gives stable recall under continuous inserts and beats IVFFlat on
both latency and quality at our target scale; trade-off is build time and
memory, both of which we can afford here.

Both DROP and CREATE are CONCURRENT so this migration can be applied to a
live database without taking a write lock on the items table.

Revision ID: 002_hnsw_index
Revises: 001_initial_schema
"""

from __future__ import annotations

from alembic import op


revision = "002_hnsw_index"
down_revision = "001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_items_embedding_ivfflat")
    op.execute(
        """
        CREATE INDEX CONCURRENTLY ix_items_embedding_hnsw
        ON items USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        WHERE status = 'active' AND embedding IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_items_embedding_hnsw")
    op.execute(
        """
        CREATE INDEX CONCURRENTLY ix_items_embedding_ivfflat
        ON items USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100)
        WHERE status = 'active' AND embedding IS NOT NULL
        """
    )
