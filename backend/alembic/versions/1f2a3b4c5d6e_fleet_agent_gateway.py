"""fleet_agent_gateway"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "1f2a3b4c5d6e"
down_revision = "9d8b0f2c4a11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("UPDATE workers SET agent_id = 'agt_worker_' || id::text WHERE agent_id IS NULL")

    op.create_table(
        "agents",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("worker_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("hostname", sa.String(length=180), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("connectivity_status", sa.String(length=30), nullable=False),
        sa.Column("administrative_status", sa.String(length=40), nullable=False),
        sa.Column("health_status", sa.String(length=30), nullable=False),
        sa.Column("occupancy_status", sa.String(length=30), nullable=False),
        sa.Column("current_version", sa.String(length=80), nullable=True),
        sa.Column("desired_version", sa.String(length=80), nullable=True),
        sa.Column("protocol_version", sa.String(length=20), nullable=True),
        sa.Column("local_identity", sa.String(length=180), nullable=True),
        sa.Column("machine_fingerprint", sa.String(length=180), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["worker_id"], ["workers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in [
        "worker_id",
        "hostname",
        "connectivity_status",
        "administrative_status",
        "health_status",
        "occupancy_status",
        "local_identity",
        "machine_fingerprint",
        "last_seen_at",
    ]:
        op.create_index(f"ix_agents_{column}", "agents", [column], unique=column in {"worker_id", "local_identity", "machine_fingerprint"})

    op.execute(
        """
        INSERT INTO agents (
            id, worker_id, name, hostname, enabled, connectivity_status,
            administrative_status, health_status, occupancy_status,
            current_version, local_identity, machine_fingerprint,
            created_at, updated_at, last_seen_at, disabled_at
        )
        SELECT
            agent_id,
            id,
            name,
            hostname,
            COALESCE(is_active, true),
            CASE WHEN status IN ('online', 'busy') THEN 'online'
                 WHEN status = 'disabled' THEN 'offline'
                 ELSE 'offline' END,
            CASE WHEN COALESCE(is_active, true) = false OR status = 'disabled' THEN 'disabled'
                 ELSE 'enabled' END,
            'healthy',
            CASE WHEN status = 'busy' THEN 'busy' ELSE 'idle' END,
            agent_version,
            machine_id,
            machine_id,
            created_at,
            updated_at,
            last_heartbeat_at,
            CASE WHEN COALESCE(is_active, true) = false OR status = 'disabled' THEN updated_at ELSE NULL END
        FROM workers
        ON CONFLICT (id) DO NOTHING
        """
    )

    op.create_table(
        "agent_instances",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("process_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("shutdown_reason", sa.Text(), nullable=True),
        sa.Column("agent_version", sa.String(length=80), nullable=True),
        sa.Column("negotiated_protocol_version", sa.String(length=20), nullable=True),
        sa.Column("connection_id", sa.String(length=80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", name="uq_agent_instance_connection_id"),
    )
    for column in ["agent_id", "connected_at", "last_seen_at", "disconnected_at", "connection_id"]:
        op.create_index(f"ix_agent_instances_{column}", "agent_instances", [column], unique=False)

    op.create_table(
        "agent_registration_tokens",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("used_by_agent_id", sa.String(length=80), nullable=True),
        sa.Column("created_by", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.ForeignKeyConstraint(["used_by_agent_id"], ["agents.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_agent_registration_token_hash"),
    )
    for column in ["token_hash", "status", "expires_at", "used_by_agent_id"]:
        op.create_index(f"ix_agent_registration_tokens_{column}", "agent_registration_tokens", [column], unique=False)

    op.create_table(
        "agent_credentials",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("credential_type", sa.String(length=50), nullable=False),
        sa.Column("public_identifier", sa.String(length=120), nullable=False),
        sa.Column("secret_hash", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("public_identifier", name="uq_agent_credential_public_identifier"),
    )
    for column in ["agent_id", "public_identifier", "status", "expires_at"]:
        op.create_index(f"ix_agent_credentials_{column}", "agent_credentials", [column], unique=False)

    op.create_table(
        "agent_machine_profiles",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("hostname", sa.String(length=180), nullable=False),
        sa.Column("operating_system", sa.String(length=120), nullable=True),
        sa.Column("operating_system_version", sa.String(length=120), nullable=True),
        sa.Column("operating_system_build", sa.String(length=120), nullable=True),
        sa.Column("architecture", sa.String(length=80), nullable=True),
        sa.Column("cpu_model", sa.Text(), nullable=True),
        sa.Column("physical_cores", sa.Integer(), nullable=True),
        sa.Column("logical_processors", sa.Integer(), nullable=True),
        sa.Column("total_memory_mb", sa.Integer(), nullable=True),
        sa.Column("disk_volumes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("network_summary", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("interactive_session_supported", sa.Boolean(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["agent_id", "agent_instance_id", "observed_at", "expires_at"]:
        op.create_index(f"ix_agent_machine_profiles_{column}", "agent_machine_profiles", [column], unique=False)

    op.create_table(
        "agent_resource_snapshots",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("cpu_usage_percentage", sa.Float(), nullable=True),
        sa.Column("memory_total_mb", sa.Integer(), nullable=True),
        sa.Column("memory_available_mb", sa.Integer(), nullable=True),
        sa.Column("memory_usage_percentage", sa.Float(), nullable=True),
        sa.Column("disk_free_mb", sa.Integer(), nullable=True),
        sa.Column("disk_usage_percentage", sa.Float(), nullable=True),
        sa.Column("process_count", sa.Integer(), nullable=True),
        sa.Column("uptime_seconds", sa.Integer(), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["agent_id", "agent_instance_id", "observed_at", "expires_at"]:
        op.create_index(f"ix_agent_resource_snapshots_{column}", "agent_resource_snapshots", [column], unique=False)

    op.create_table(
        "agent_capabilities",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("key", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("version", sa.String(length=120), nullable=True),
        sa.Column("attributes", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("source", sa.String(length=120), nullable=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["agent_id", "agent_instance_id", "key", "status", "observed_at", "expires_at", "is_current"]:
        op.create_index(f"ix_agent_capabilities_{column}", "agent_capabilities", [column], unique=False)

    op.create_table(
        "agent_configurations",
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("heartbeat_interval_seconds", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("stale_after_seconds", sa.Integer(), nullable=False, server_default="90"),
        sa.Column("offline_after_seconds", sa.Integer(), nullable=False, server_default="180"),
        sa.Column("administrator_pool_limits", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled_pools", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("allowlist_capabilities", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("maintenance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("desired_version", sa.String(length=80), nullable=True),
        sa.Column("restrictions", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("agent_id"),
    )
    op.execute(
        """
        INSERT INTO agent_configurations (agent_id, administrator_pool_limits, enabled_pools)
        SELECT id, '{"interactive": null, "background": null, "browser": null}'::jsonb, '["interactive", "background", "browser"]'::jsonb
        FROM agents
        ON CONFLICT (agent_id) DO NOTHING
        """
    )

    op.create_table(
        "agent_pools",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("pool_type", sa.String(length=40), nullable=False),
        sa.Column("recommended_total", sa.Integer(), nullable=True),
        sa.Column("administrator_total", sa.Integer(), nullable=True),
        sa.Column("effective_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("available", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["agent_id", "pool_type", "observed_at", "is_current"]:
        op.create_index(f"ix_agent_pools_{column}", "agent_pools", [column], unique=False)

    op.create_table(
        "interactive_session_snapshots",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("available", sa.Boolean(), nullable=True),
        sa.Column("locked", sa.Boolean(), nullable=True),
        sa.Column("user", sa.String(length=255), nullable=True),
        sa.Column("session_id", sa.String(length=120), nullable=True),
        sa.Column("session_type", sa.String(length=80), nullable=True),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["agent_id", "agent_instance_id", "state", "observed_at", "expires_at"]:
        op.create_index(f"ix_interactive_session_snapshots_{column}", "interactive_session_snapshots", [column], unique=False)

    op.create_table(
        "agent_connections",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=False),
        sa.Column("connection_id", sa.String(length=80), nullable=False),
        sa.Column("protocol_version", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("connected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_reason", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connection_id", name="uq_agent_connection_connection_id"),
    )
    for column in ["agent_id", "agent_instance_id", "connection_id", "status", "connected_at", "disconnected_at"]:
        op.create_index(f"ix_agent_connections_{column}", "agent_connections", [column], unique=False)

    op.create_table(
        "agent_diagnostics",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("agent_id", sa.String(length=80), nullable=False),
        sa.Column("agent_instance_id", sa.String(length=80), nullable=True),
        sa.Column("request_command_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("details", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("artifact_id", sa.String(length=80), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["agent_instance_id"], ["agent_instances.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["request_command_id"], ["agent_commands.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ["agent_id", "agent_instance_id", "request_command_id", "status", "requested_at"]:
        op.create_index(f"ix_agent_diagnostics_{column}", "agent_diagnostics", [column], unique=False)

    op.drop_constraint("uq_agent_command_sequence", "agent_commands", type_="unique")
    op.alter_column("agent_commands", "agent_instance_id", existing_type=sa.String(length=120), nullable=True)
    op.create_unique_constraint("uq_agent_command_agent_sequence", "agent_commands", ["agent_id", "command_sequence"])


def downgrade() -> None:
    op.drop_constraint("uq_agent_command_agent_sequence", "agent_commands", type_="unique")
    op.alter_column("agent_commands", "agent_instance_id", existing_type=sa.String(length=120), nullable=False)
    op.create_unique_constraint("uq_agent_command_sequence", "agent_commands", ["agent_instance_id", "command_sequence"])

    for column in ["agent_id", "agent_instance_id", "request_command_id", "status", "requested_at"]:
        op.drop_index(f"ix_agent_diagnostics_{column}", table_name="agent_diagnostics")
    op.drop_table("agent_diagnostics")

    for column in ["agent_id", "agent_instance_id", "connection_id", "status", "connected_at", "disconnected_at"]:
        op.drop_index(f"ix_agent_connections_{column}", table_name="agent_connections")
    op.drop_table("agent_connections")

    for column in ["agent_id", "agent_instance_id", "state", "observed_at", "expires_at"]:
        op.drop_index(f"ix_interactive_session_snapshots_{column}", table_name="interactive_session_snapshots")
    op.drop_table("interactive_session_snapshots")

    for column in ["agent_id", "pool_type", "observed_at", "is_current"]:
        op.drop_index(f"ix_agent_pools_{column}", table_name="agent_pools")
    op.drop_table("agent_pools")

    op.drop_table("agent_configurations")

    for column in ["agent_id", "agent_instance_id", "key", "status", "observed_at", "expires_at", "is_current"]:
        op.drop_index(f"ix_agent_capabilities_{column}", table_name="agent_capabilities")
    op.drop_table("agent_capabilities")

    for column in ["agent_id", "agent_instance_id", "observed_at", "expires_at"]:
        op.drop_index(f"ix_agent_resource_snapshots_{column}", table_name="agent_resource_snapshots")
    op.drop_table("agent_resource_snapshots")

    for column in ["agent_id", "agent_instance_id", "observed_at", "expires_at"]:
        op.drop_index(f"ix_agent_machine_profiles_{column}", table_name="agent_machine_profiles")
    op.drop_table("agent_machine_profiles")

    for column in ["agent_id", "public_identifier", "status", "expires_at"]:
        op.drop_index(f"ix_agent_credentials_{column}", table_name="agent_credentials")
    op.drop_table("agent_credentials")

    for column in ["token_hash", "status", "expires_at", "used_by_agent_id"]:
        op.drop_index(f"ix_agent_registration_tokens_{column}", table_name="agent_registration_tokens")
    op.drop_table("agent_registration_tokens")

    for column in ["agent_id", "connected_at", "last_seen_at", "disconnected_at", "connection_id"]:
        op.drop_index(f"ix_agent_instances_{column}", table_name="agent_instances")
    op.drop_table("agent_instances")

    for column in [
        "worker_id",
        "hostname",
        "connectivity_status",
        "administrative_status",
        "health_status",
        "occupancy_status",
        "local_identity",
        "machine_fingerprint",
        "last_seen_at",
    ]:
        op.drop_index(f"ix_agents_{column}", table_name="agents")
    op.drop_table("agents")
