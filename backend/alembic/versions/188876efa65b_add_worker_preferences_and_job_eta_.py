"""add_worker_preferences_and_job_eta_fields"""

from alembic import op
import sqlalchemy as sa

revision = '188876efa65b'
down_revision = '20260314_0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create automation_worker_preferences table
    op.create_table(
        'automation_worker_preferences',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('automation_id', sa.Integer(), nullable=False),
        sa.Column('worker_id', sa.Integer(), nullable=False),
        sa.Column('priority_order', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['automation_id'], ['automations.id'], ),
        sa.ForeignKeyConstraint(['worker_id'], ['workers.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('automation_id', 'worker_id', name='uq_automation_worker')
    )
    op.create_index(op.f('ix_automation_worker_preferences_id'), 'automation_worker_preferences', ['id'], unique=False)
    op.create_index(op.f('ix_automation_worker_preferences_automation_id'), 'automation_worker_preferences', ['automation_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_automation_worker_preferences_automation_id'), table_name='automation_worker_preferences')
    op.drop_index(op.f('ix_automation_worker_preferences_id'), table_name='automation_worker_preferences')
    op.drop_table('automation_worker_preferences')
