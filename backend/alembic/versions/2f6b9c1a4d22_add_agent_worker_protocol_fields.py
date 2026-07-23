"""add_agent_worker_protocol_fields"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "2f6b9c1a4d22"
down_revision = "0977aba80995"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workers", sa.Column("agent_id", sa.String(length=80), nullable=True))
    op.add_column("workers", sa.Column("machine_id", sa.String(length=120), nullable=True))
    op.add_column("workers", sa.Column("device_token", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("agent_version", sa.String(length=40), nullable=True))
    op.add_column("workers", sa.Column("os", sa.Text(), nullable=True))
    op.add_column("workers", sa.Column("architecture", sa.String(length=80), nullable=True))
    op.add_column("workers", sa.Column("capabilities_json", JSONB(), nullable=True))
    op.add_column("workers", sa.Column("last_payload_json", JSONB(), nullable=True))
    op.create_index(op.f("ix_workers_agent_id"), "workers", ["agent_id"], unique=True)
    op.create_index(op.f("ix_workers_machine_id"), "workers", ["machine_id"], unique=True)

    op.add_column("automations", sa.Column("package_url", sa.Text(), nullable=True))
    op.add_column("automations", sa.Column("package_sha256", sa.String(length=120), nullable=True))


def downgrade() -> None:
    op.drop_column("automations", "package_sha256")
    op.drop_column("automations", "package_url")

    op.drop_index(op.f("ix_workers_machine_id"), table_name="workers")
    op.drop_index(op.f("ix_workers_agent_id"), table_name="workers")
    op.drop_column("workers", "last_payload_json")
    op.drop_column("workers", "capabilities_json")
    op.drop_column("workers", "architecture")
    op.drop_column("workers", "os")
    op.drop_column("workers", "agent_version")
    op.drop_column("workers", "device_token")
    op.drop_column("workers", "machine_id")
    op.drop_column("workers", "agent_id")
