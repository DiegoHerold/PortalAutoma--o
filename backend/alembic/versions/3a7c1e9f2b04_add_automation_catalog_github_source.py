"""add_automation_catalog_github_source"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "3a7c1e9f2b04"
down_revision = "2f6b9c1a4d22"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("automations", sa.Column("key", sa.String(length=180), nullable=True))
    op.create_index(op.f("ix_automations_key"), "automations", ["key"], unique=True)

    op.create_table(
        "github_integrations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("installation_id", sa.Integer(), nullable=False),
        sa.Column("account_login", sa.String(length=200), nullable=False),
        sa.Column("account_type", sa.String(length=30), nullable=False),
        sa.Column("connected_by_user_id", sa.Integer(), nullable=True),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["connected_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_github_integrations_id"), "github_integrations", ["id"], unique=False)
    op.create_index(
        op.f("ix_github_integrations_installation_id"),
        "github_integrations",
        ["installation_id"],
        unique=True,
    )

    op.create_table(
        "automation_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=30), nullable=False),
        sa.Column("integration_id", sa.Integer(), nullable=True),
        sa.Column("owner", sa.String(length=200), nullable=True),
        sa.Column("repository", sa.String(length=200), nullable=True),
        sa.Column("branch", sa.String(length=200), nullable=True),
        sa.Column("automation_path", sa.Text(), nullable=True),
        sa.Column("manifest_path", sa.Text(), nullable=True),
        sa.Column("workspace_path", sa.Text(), nullable=True),
        sa.Column("last_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sync_status", sa.String(length=30), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_sha256", sa.String(length=120), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["github_integrations.id"]),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_sources_id"), "automation_sources", ["id"], unique=False)
    op.create_index(
        op.f("ix_automation_sources_automation_id"), "automation_sources", ["automation_id"], unique=False
    )

    op.create_table(
        "automation_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("automation_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("manifest", JSONB(), nullable=False),
        sa.Column("manifest_schema_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("runtime_id", sa.String(length=80), nullable=False),
        sa.Column("runtime_version", sa.String(length=40), nullable=True),
        sa.Column("entrypoint_type", sa.String(length=50), nullable=False),
        sa.Column("entrypoint", JSONB(), nullable=False),
        sa.Column("application_type", sa.String(length=20), nullable=False, server_default="source"),
        sa.Column("application_path", sa.Text(), nullable=True),
        sa.Column("artifact_bucket", sa.String(length=200), nullable=False),
        sa.Column("artifact_object_key", sa.Text(), nullable=False),
        sa.Column("artifact_size", sa.Integer(), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=120), nullable=False),
        sa.Column("source_commit_sha", sa.String(length=64), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="validating"),
        sa.Column("validation_errors", JSONB(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["automation_id"], ["automations.id"]),
        sa.ForeignKeyConstraint(["source_id"], ["automation_sources.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("automation_id", "version", name="uq_automation_version"),
    )
    op.create_index(op.f("ix_automation_versions_id"), "automation_versions", ["id"], unique=False)
    op.create_index(
        op.f("ix_automation_versions_automation_id"), "automation_versions", ["automation_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_automation_versions_automation_id"), table_name="automation_versions")
    op.drop_index(op.f("ix_automation_versions_id"), table_name="automation_versions")
    op.drop_table("automation_versions")

    op.drop_index(op.f("ix_automation_sources_automation_id"), table_name="automation_sources")
    op.drop_index(op.f("ix_automation_sources_id"), table_name="automation_sources")
    op.drop_table("automation_sources")

    op.drop_index(op.f("ix_github_integrations_installation_id"), table_name="github_integrations")
    op.drop_index(op.f("ix_github_integrations_id"), table_name="github_integrations")
    op.drop_table("github_integrations")

    op.drop_index(op.f("ix_automations_key"), table_name="automations")
    op.drop_column("automations", "key")
