"""expand_audit_log_fields"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '0977aba80995'
down_revision = '188876efa65b'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add new columns to audit_logs
    op.add_column('audit_logs', sa.Column('actor_type', sa.String(50), nullable=True))
    op.add_column('audit_logs', sa.Column('before', JSONB, nullable=True))
    op.add_column('audit_logs', sa.Column('after', JSONB, nullable=True))
    
    # Add indexes for better query performance
    op.create_index(op.f('ix_audit_logs_event_type'), 'audit_logs', ['event_type'], unique=False)
    op.create_index(op.f('ix_audit_logs_actor_email'), 'audit_logs', ['actor_email'], unique=False)
    op.create_index(op.f('ix_audit_logs_resource_type'), 'audit_logs', ['resource_type'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_audit_logs_resource_type'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_actor_email'), table_name='audit_logs')
    op.drop_index(op.f('ix_audit_logs_event_type'), table_name='audit_logs')
    op.drop_column('audit_logs', 'after')
    op.drop_column('audit_logs', 'before')
    op.drop_column('audit_logs', 'actor_type')

