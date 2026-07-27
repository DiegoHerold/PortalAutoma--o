"""catalog_persistence_reliability"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "9d8b0f2c4a11"
down_revision = "7c1d8e4f9a3b"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("automations", sa.Column("status", sa.String(length=30), nullable=False, server_default="active"))
    op.add_column("automations", sa.Column("tags_json", JSONB(), nullable=True))
    op.add_column("automations", sa.Column("created_by_user_id", sa.Integer(), nullable=True))
    op.create_index(op.f("ix_automations_status"), "automations", ["status"], unique=False)
    op.create_foreign_key("fk_automations_created_by_user_id", "automations", "users", ["created_by_user_id"], ["id"])
    op.alter_column("automations", "status", server_default=None)

    op.create_table(
        "stored_objects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("bucket", sa.String(length=200), nullable=False),
        sa.Column("object_key", sa.Text(), nullable=False),
        sa.Column("content_type", sa.String(length=120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("etag", sa.String(length=180), nullable=True),
        sa.Column("provider", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_stored_object_location"),
    )
    op.create_index(op.f("ix_stored_objects_sha256"), "stored_objects", ["sha256"], unique=False)
    op.create_index(op.f("ix_stored_objects_status"), "stored_objects", ["status"], unique=False)

    op.create_table(
        "upload_sessions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stored_object_id", sa.String(length=36), nullable=False),
        sa.Column("upload_url", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expected_size_bytes", sa.Integer(), nullable=True),
        sa.Column("expected_sha256", sa.String(length=64), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("aborted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["stored_object_id"], ["stored_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_upload_sessions_stored_object_id"), "upload_sessions", ["stored_object_id"], unique=False)
    op.create_index(op.f("ix_upload_sessions_status"), "upload_sessions", ["status"], unique=False)
    op.create_index(op.f("ix_upload_sessions_expires_at"), "upload_sessions", ["expires_at"], unique=False)

    op.create_table(
        "runtimes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runtimes_key"), "runtimes", ["key"], unique=True)
    op.create_index(op.f("ix_runtimes_status"), "runtimes", ["status"], unique=False)

    op.create_table(
        "runtime_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("runtime_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.String(length=50), nullable=False),
        sa.Column("operating_system", sa.String(length=80), nullable=False),
        sa.Column("architecture", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("minimum_agent_version", sa.String(length=50), nullable=True),
        sa.Column("supported_entrypoints", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("supported_execution_modes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["runtime_id"], ["runtimes.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("runtime_id", "version", "operating_system", "architecture", name="uq_runtime_version_platform"),
    )
    op.create_index(op.f("ix_runtime_versions_runtime_id"), "runtime_versions", ["runtime_id"], unique=False)
    op.create_index(op.f("ix_runtime_versions_status"), "runtime_versions", ["status"], unique=False)

    op.create_table(
        "automation_manifests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("automation_version_id", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.String(length=20), nullable=False),
        sa.Column("raw_content", sa.Text(), nullable=False),
        sa.Column("normalized_content", JSONB(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("validation_status", sa.String(length=30), nullable=False),
        sa.Column("validation_errors", JSONB(), nullable=True),
        sa.Column("validator_version", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["automation_version_id"], ["automation_versions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_manifests_automation_version_id"), "automation_manifests", ["automation_version_id"], unique=False)
    op.create_index(op.f("ix_automation_manifests_content_hash"), "automation_manifests", ["content_hash"], unique=False)

    op.create_table(
        "automation_packages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("automation_version_id", sa.Integer(), nullable=False),
        sa.Column("stored_object_id", sa.String(length=36), nullable=False),
        sa.Column("package_format", sa.String(length=20), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("signature_algorithm", sa.String(length=80), nullable=True),
        sa.Column("signing_key_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("validation_result", JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["automation_version_id"], ["automation_versions.id"]),
        sa.ForeignKeyConstraint(["stored_object_id"], ["stored_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_automation_packages_automation_version_id"), "automation_packages", ["automation_version_id"], unique=False)
    op.create_index(op.f("ix_automation_packages_stored_object_id"), "automation_packages", ["stored_object_id"], unique=False)
    op.create_index(op.f("ix_automation_packages_sha256"), "automation_packages", ["sha256"], unique=False)
    op.create_index(op.f("ix_automation_packages_status"), "automation_packages", ["status"], unique=False)

    op.create_table(
        "runtime_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("runtime_version_id", sa.String(length=36), nullable=False),
        sa.Column("stored_object_id", sa.String(length=36), nullable=False),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=True),
        sa.Column("signature_algorithm", sa.String(length=80), nullable=True),
        sa.Column("signing_key_id", sa.String(length=120), nullable=True),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["runtime_version_id"], ["runtime_versions.id"]),
        sa.ForeignKeyConstraint(["stored_object_id"], ["stored_objects.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_runtime_artifacts_runtime_version_id"), "runtime_artifacts", ["runtime_version_id"], unique=False)
    op.create_index(op.f("ix_runtime_artifacts_stored_object_id"), "runtime_artifacts", ["stored_object_id"], unique=False)
    op.create_index(op.f("ix_runtime_artifacts_sha256"), "runtime_artifacts", ["sha256"], unique=False)
    op.create_index(op.f("ix_runtime_artifacts_status"), "runtime_artifacts", ["status"], unique=False)

    op.add_column("automation_versions", sa.Column("manifest_id", sa.String(length=36), nullable=True))
    op.add_column("automation_versions", sa.Column("package_id", sa.String(length=36), nullable=True))
    op.add_column("automation_versions", sa.Column("runtime_version_id", sa.String(length=36), nullable=True))
    op.add_column("automation_versions", sa.Column("release_notes", sa.Text(), nullable=True))
    op.add_column("automation_versions", sa.Column("source_repository", sa.Text(), nullable=True))
    op.add_column("automation_versions", sa.Column("source_branch", sa.String(length=200), nullable=True))
    op.add_column("automation_versions", sa.Column("source_tag", sa.String(length=200), nullable=True))
    op.add_column("automation_versions", sa.Column("build_id", sa.String(length=120), nullable=True))
    op.add_column("automation_versions", sa.Column("created_by", sa.String(length=255), nullable=True))
    op.add_column("automation_versions", sa.Column("published_by", sa.String(length=255), nullable=True))
    op.add_column("automation_versions", sa.Column("deprecated_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("automation_versions", sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_automation_versions_manifest_id", "automation_versions", "automation_manifests", ["manifest_id"], ["id"])
    op.create_foreign_key("fk_automation_versions_package_id", "automation_versions", "automation_packages", ["package_id"], ["id"])
    op.create_foreign_key("fk_automation_versions_runtime_version_id", "automation_versions", "runtime_versions", ["runtime_version_id"], ["id"])

    op.create_table(
        "outbox_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("topic", sa.String(length=120), nullable=False),
        sa.Column("message_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_type", sa.String(length=120), nullable=False),
        sa.Column("aggregate_id", sa.String(length=120), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("causation_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["topic", "message_type", "aggregate_type", "aggregate_id", "status", "available_at", "correlation_id", "causation_id"]:
        op.create_index(f"ix_outbox_messages_{column}", "outbox_messages", [column], unique=False)

    op.create_table(
        "inbox_messages",
        sa.Column("message_id", sa.String(length=120), nullable=False),
        sa.Column("source", sa.String(length=120), nullable=False),
        sa.Column("source_id", sa.String(length=120), nullable=True),
        sa.Column("message_type", sa.String(length=120), nullable=False),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processing_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("message_id"),
    )
    for column in ["source", "source_id", "message_type", "status"]:
        op.create_index(f"ix_inbox_messages_{column}", "inbox_messages", [column], unique=False)

    op.create_table(
        "agent_commands",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("agent_id", sa.String(length=120), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=120), nullable=False),
        sa.Column("command_sequence", sa.Integer(), nullable=False),
        sa.Column("message_type", sa.String(length=120), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("correlation_id", sa.String(length=120), nullable=True),
        sa.Column("causation_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("available_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("agent_instance_id", "command_sequence", name="uq_agent_command_sequence"),
    )
    for column in ["agent_id", "agent_instance_id", "message_type", "status", "available_at", "expires_at", "correlation_id", "causation_id"]:
        op.create_index(f"ix_agent_commands_{column}", "agent_commands", [column], unique=False)

    op.create_table(
        "idempotency_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=180), nullable=False),
        sa.Column("scope", sa.String(length=180), nullable=False),
        sa.Column("request_hash", sa.String(length=64), nullable=False),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_payload", JSONB(), nullable=True),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scope", "key", name="uq_idempotency_scope_key"),
    )
    op.create_index(op.f("ix_idempotency_records_expires_at"), "idempotency_records", ["expires_at"], unique=False)

    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("actor_type", sa.String(length=50), nullable=False),
        sa.Column("actor_id", sa.String(length=255), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=120), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=False),
        sa.Column("before", JSONB(), nullable=True),
        sa.Column("after", JSONB(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("ip", sa.String(length=80), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["actor_type", "actor_id", "action", "resource_type", "resource_id"]:
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column], unique=False)


def downgrade() -> None:
    for column in ["actor_type", "actor_id", "action", "resource_type", "resource_id"]:
        op.drop_index(f"ix_audit_events_{column}", table_name="audit_events")
    op.drop_table("audit_events")

    op.drop_index(op.f("ix_idempotency_records_expires_at"), table_name="idempotency_records")
    op.drop_table("idempotency_records")

    for column in ["agent_id", "agent_instance_id", "message_type", "status", "available_at", "expires_at", "correlation_id", "causation_id"]:
        op.drop_index(f"ix_agent_commands_{column}", table_name="agent_commands")
    op.drop_table("agent_commands")

    for column in ["source", "source_id", "message_type", "status"]:
        op.drop_index(f"ix_inbox_messages_{column}", table_name="inbox_messages")
    op.drop_table("inbox_messages")

    for column in ["topic", "message_type", "aggregate_type", "aggregate_id", "status", "available_at", "correlation_id", "causation_id"]:
        op.drop_index(f"ix_outbox_messages_{column}", table_name="outbox_messages")
    op.drop_table("outbox_messages")

    op.drop_constraint("fk_automation_versions_runtime_version_id", "automation_versions", type_="foreignkey")
    op.drop_constraint("fk_automation_versions_package_id", "automation_versions", type_="foreignkey")
    op.drop_constraint("fk_automation_versions_manifest_id", "automation_versions", type_="foreignkey")
    for column in [
        "blocked_at",
        "deprecated_at",
        "published_by",
        "created_by",
        "build_id",
        "source_tag",
        "source_branch",
        "source_repository",
        "release_notes",
        "runtime_version_id",
        "package_id",
        "manifest_id",
    ]:
        op.drop_column("automation_versions", column)

    op.drop_index(op.f("ix_runtime_artifacts_status"), table_name="runtime_artifacts")
    op.drop_index(op.f("ix_runtime_artifacts_sha256"), table_name="runtime_artifacts")
    op.drop_index(op.f("ix_runtime_artifacts_stored_object_id"), table_name="runtime_artifacts")
    op.drop_index(op.f("ix_runtime_artifacts_runtime_version_id"), table_name="runtime_artifacts")
    op.drop_table("runtime_artifacts")

    op.drop_index(op.f("ix_automation_packages_status"), table_name="automation_packages")
    op.drop_index(op.f("ix_automation_packages_sha256"), table_name="automation_packages")
    op.drop_index(op.f("ix_automation_packages_stored_object_id"), table_name="automation_packages")
    op.drop_index(op.f("ix_automation_packages_automation_version_id"), table_name="automation_packages")
    op.drop_table("automation_packages")

    op.drop_index(op.f("ix_automation_manifests_content_hash"), table_name="automation_manifests")
    op.drop_index(op.f("ix_automation_manifests_automation_version_id"), table_name="automation_manifests")
    op.drop_table("automation_manifests")

    op.drop_index(op.f("ix_runtime_versions_status"), table_name="runtime_versions")
    op.drop_index(op.f("ix_runtime_versions_runtime_id"), table_name="runtime_versions")
    op.drop_table("runtime_versions")

    op.drop_index(op.f("ix_runtimes_status"), table_name="runtimes")
    op.drop_index(op.f("ix_runtimes_key"), table_name="runtimes")
    op.drop_table("runtimes")

    op.drop_index(op.f("ix_upload_sessions_expires_at"), table_name="upload_sessions")
    op.drop_index(op.f("ix_upload_sessions_status"), table_name="upload_sessions")
    op.drop_index(op.f("ix_upload_sessions_stored_object_id"), table_name="upload_sessions")
    op.drop_table("upload_sessions")

    op.drop_index(op.f("ix_stored_objects_status"), table_name="stored_objects")
    op.drop_index(op.f("ix_stored_objects_sha256"), table_name="stored_objects")
    op.drop_table("stored_objects")

    op.drop_constraint("fk_automations_created_by_user_id", "automations", type_="foreignkey")
    op.drop_index(op.f("ix_automations_status"), table_name="automations")
    op.drop_column("automations", "created_by_user_id")
    op.drop_column("automations", "tags_json")
    op.drop_column("automations", "status")
