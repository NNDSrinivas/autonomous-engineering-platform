"""Add navi_memory table for conversational memory

Revision ID: 0018_navi_memory
Revises: 0017_ai_feedback
Create Date: 2025-11-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import VECTOR

# revision identifiers, used by Alembic.
revision = '0018_navi_memory'
down_revision = '0017_ai_feedback'
branch_labels = None
depends_on = None


def upgrade():
    """Create navi_memory table for NAVI conversational memory"""
    op.create_table(
        'navi_memory',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False,
                  comment='Memory category: profile|workspace|task|interaction'),
        sa.Column('scope', sa.String(length=255), nullable=True,
                  comment='Scope identifier: workspace path, task ID, etc.'),
        sa.Column('title', sa.Text(), nullable=True,
                  comment='Human-readable title for the memory'),
        sa.Column('content', sa.Text(), nullable=False,
                  comment='Memory content (human-readable)'),
        sa.Column('embedding_vec', VECTOR(1536), nullable=True,
                  comment='OpenAI embedding for semantic search'),
        sa.Column('meta_json', sa.JSON(), nullable=True,
                  comment='Additional metadata: tags, source, etc.'),
        sa.Column('importance', sa.Integer(), nullable=False, server_default='3',
                  comment='Importance score 1-5 for retrieval prioritization'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Indexes for efficient queries
    op.create_index('idx_navi_memory_user', 'navi_memory', ['user_id'])
    op.create_index('idx_navi_memory_category', 'navi_memory', ['user_id', 'category'])
    op.create_index('idx_navi_memory_scope', 'navi_memory', ['user_id', 'scope'])
    op.create_index('idx_navi_memory_importance', 'navi_memory', ['importance'])
    
    # pgvector HNSW index for fast semantic search
    op.execute("""
        CREATE INDEX idx_navi_memory_embedding 
        ON navi_memory 
        USING hnsw (embedding_vec vector_cosine_ops)
    """)


def downgrade():
    """Drop navi_memory table"""
    op.drop_index('idx_navi_memory_embedding', 'navi_memory')
    op.drop_index('idx_navi_memory_importance', 'navi_memory')
    op.drop_index('idx_navi_memory_scope', 'navi_memory')
    op.drop_index('idx_navi_memory_category', 'navi_memory')
    op.drop_index('idx_navi_memory_user', 'navi_memory')
    op.drop_table('navi_memory')
