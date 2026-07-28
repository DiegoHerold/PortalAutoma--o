"""access_governance_final"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "5a6b7c8d9e0f"
down_revision = "4f5a6b7c8d9e"
branch_labels = None
depends_on = None


PERMISSIONS = (
    "automation.read",
    "automation.create",
    "automation.update",
    "automation.publish",
    "automation.block",
    "runtime.read",
    "runtime.manage",
    "agent.read",
    "agent.manage",
    "agent.disable",
    "agent.update",
    "agent.diagnose",
    "execution.read",
    "execution.create",
    "execution.cancel",
    "execution.retry",
    "flow.read",
    "flow.create",
    "flow.update",
    "flow.publish",
    "flow.execute",
    "schedule.read",
    "schedule.create",
    "schedule.update",
    "schedule.trigger",
    "artifact.read",
    "artifact.download",
    "audit.read",
    "secret.read_metadata",
    "secret.manage",
    "admin.users",
    "admin.roles",
    "admin.system",
)


def upgrade() -> None:
    op.create_table(
        "access_organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_access_organizations_key", "access_organizations", ["key"], unique=True)
    op.create_index("ix_access_organizations_status", "access_organizations", ["status"])
    op.execute(
        "INSERT INTO access_organizations (key, name, status) "
        "VALUES ('default', 'Default Organization', 'active') "
        "ON CONFLICT (key) DO NOTHING"
    )

    op.add_column("roles", sa.Column("status", sa.String(length=40), nullable=False, server_default="active"))
    op.add_column("roles", sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("UPDATE roles SET is_system = true WHERE slug IN ('admin', 'manager', 'operator', 'viewer')")

    op.add_column("users", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("status", sa.String(length=40), nullable=False, server_default="active"))
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("disabled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("locked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("users", sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE users SET status = CASE WHEN is_active THEN 'active' ELSE 'disabled' END")
    op.execute("UPDATE users SET disabled_at = now() WHERE is_active = false AND disabled_at IS NULL")
    op.execute("UPDATE users SET organization_id = (SELECT id FROM access_organizations WHERE key = 'default') WHERE organization_id IS NULL")
    op.create_foreign_key("fk_users_organization_id", "users", "access_organizations", ["organization_id"], ["id"])
    op.create_index("ix_users_organization_id", "users", ["organization_id"])
    op.create_index("ix_users_status", "users", ["status"])

    op.create_table(
        "permissions",
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("key"),
    )
    permissions_table = sa.table("permissions", sa.column("key", sa.String), sa.column("description", sa.Text))
    op.bulk_insert(permissions_table, [{"key": key, "description": None} for key in PERMISSIONS])

    op.create_table(
        "role_permissions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("permission_key", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["permission_key"], ["permissions.key"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission_key", name="uq_role_permissions_role_permission"),
    )
    op.create_index("ix_role_permissions_role_id", "role_permissions", ["role_id"])
    op.create_index("ix_role_permissions_permission_key", "role_permissions", ["permission_key"])
    _seed_role_permissions()

    op.create_table(
        "user_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["access_organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "role_id", "organization_id", name="uq_user_roles_scope"),
    )
    op.create_index("ix_user_roles_user_id", "user_roles", ["user_id"])
    op.create_index("ix_user_roles_role_id", "user_roles", ["role_id"])
    op.create_index("ix_user_roles_organization_id", "user_roles", ["organization_id"])
    op.execute(
        "INSERT INTO user_roles (user_id, role_id, organization_id) "
        "SELECT id, role_id, organization_id FROM users "
        "ON CONFLICT ON CONSTRAINT uq_user_roles_scope DO NOTHING"
    )

    op.create_table(
        "access_teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=False),
        sa.Column("key", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["access_organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_access_teams_org_key"),
    )
    op.create_index("ix_access_teams_organization_id", "access_teams", ["organization_id"])
    op.create_index("ix_access_teams_status", "access_teams", ["status"])

    op.create_table(
        "access_team_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["team_id"], ["access_teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_access_team_memberships_team_user"),
    )
    op.create_index("ix_access_team_memberships_team_id", "access_team_memberships", ["team_id"])
    op.create_index("ix_access_team_memberships_user_id", "access_team_memberships", ["user_id"])

    op.create_table(
        "team_roles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["team_id"], ["access_teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "role_id", name="uq_team_roles_team_role"),
    )
    op.create_index("ix_team_roles_team_id", "team_roles", ["team_id"])
    op.create_index("ix_team_roles_role_id", "team_roles", ["role_id"])

    op.create_table(
        "service_accounts",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("credential_hash", sa.String(length=255), nullable=False),
        sa.Column("permissions", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["access_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_service_accounts_organization_id", "service_accounts", ["organization_id"])
    op.create_index("ix_service_accounts_status", "service_accounts", ["status"])

    op.alter_column("audit_events", "id", existing_type=sa.String(length=36), type_=sa.String(length=80))
    op.add_column("audit_events", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.add_column("audit_events", sa.Column("correlation_id", sa.String(length=120), nullable=True))
    op.create_foreign_key("fk_audit_events_organization_id", "audit_events", "access_organizations", ["organization_id"], ["id"])
    op.create_index("ix_audit_events_organization_id", "audit_events", ["organization_id"])
    op.create_index("ix_audit_events_correlation_id", "audit_events", ["correlation_id"])

    _create_governance_tables()
    _seed_governance_defaults()


def downgrade() -> None:
    _drop_governance_tables()

    op.drop_index("ix_audit_events_correlation_id", table_name="audit_events")
    op.drop_index("ix_audit_events_organization_id", table_name="audit_events")
    op.drop_constraint("fk_audit_events_organization_id", "audit_events", type_="foreignkey")
    op.drop_column("audit_events", "correlation_id")
    op.drop_column("audit_events", "organization_id")
    op.alter_column("audit_events", "id", existing_type=sa.String(length=80), type_=sa.String(length=36))

    op.drop_index("ix_service_accounts_status", table_name="service_accounts")
    op.drop_index("ix_service_accounts_organization_id", table_name="service_accounts")
    op.drop_table("service_accounts")

    op.drop_index("ix_team_roles_role_id", table_name="team_roles")
    op.drop_index("ix_team_roles_team_id", table_name="team_roles")
    op.drop_table("team_roles")

    op.drop_index("ix_access_team_memberships_user_id", table_name="access_team_memberships")
    op.drop_index("ix_access_team_memberships_team_id", table_name="access_team_memberships")
    op.drop_table("access_team_memberships")

    op.drop_index("ix_access_teams_status", table_name="access_teams")
    op.drop_index("ix_access_teams_organization_id", table_name="access_teams")
    op.drop_table("access_teams")

    op.drop_index("ix_user_roles_organization_id", table_name="user_roles")
    op.drop_index("ix_user_roles_role_id", table_name="user_roles")
    op.drop_index("ix_user_roles_user_id", table_name="user_roles")
    op.drop_table("user_roles")

    op.drop_index("ix_role_permissions_permission_key", table_name="role_permissions")
    op.drop_index("ix_role_permissions_role_id", table_name="role_permissions")
    op.drop_table("role_permissions")
    op.drop_table("permissions")

    op.drop_index("ix_users_status", table_name="users")
    op.drop_index("ix_users_organization_id", table_name="users")
    op.drop_constraint("fk_users_organization_id", "users", type_="foreignkey")
    for column in ["archived_at", "locked_at", "disabled_at", "last_login_at", "status", "organization_id"]:
        op.drop_column("users", column)

    op.drop_column("roles", "is_system")
    op.drop_column("roles", "status")

    op.drop_index("ix_access_organizations_status", table_name="access_organizations")
    op.drop_index("ix_access_organizations_key", table_name="access_organizations")
    op.drop_table("access_organizations")


def _create_governance_tables() -> None:
    op.create_table(
        "secrets",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="active"),
        sa.Column("current_version_id", sa.String(length=80), nullable=True),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["access_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_secrets_org_key"),
    )
    op.create_index("ix_secrets_organization_id", "secrets", ["organization_id"])
    op.create_index("ix_secrets_key", "secrets", ["key"])
    op.create_index("ix_secrets_status", "secrets", ["status"])
    op.create_index("ix_secrets_current_version_id", "secrets", ["current_version_id"])

    op.create_table(
        "secret_versions",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("secret_id", sa.String(length=80), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("encrypted_value", sa.Text(), nullable=False),
        sa.Column("encryption_key_id", sa.String(length=120), nullable=False),
        sa.Column("created_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["secret_id"], ["secrets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("secret_id", "version", name="uq_secret_versions_secret_version"),
    )
    op.create_index("ix_secret_versions_secret_id", "secret_versions", ["secret_id"])

    op.create_table(
        "secret_grants",
        sa.Column("id", sa.String(length=80), nullable=False),
        sa.Column("secret_id", sa.String(length=80), nullable=False),
        sa.Column("grantee_type", sa.String(length=80), nullable=False),
        sa.Column("grantee_id", sa.String(length=120), nullable=False),
        sa.Column("permission", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["secret_id"], ["secrets.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_secret_grants_secret_id", "secret_grants", ["secret_id"])
    op.create_index("ix_secret_grants_grantee_type", "secret_grants", ["grantee_type"])
    op.create_index("ix_secret_grants_grantee_id", "secret_grants", ["grantee_id"])

    op.create_table(
        "system_limits",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("key", sa.String(length=160), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("unit", sa.String(length=40), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("metadata", JSONB(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["access_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "key", name="uq_system_limits_scope_key"),
    )
    op.create_index("ix_system_limits_organization_id", "system_limits", ["organization_id"])
    op.create_index("ix_system_limits_key", "system_limits", ["key"])

    op.create_table(
        "retention_policies",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("organization_id", sa.Integer(), nullable=True),
        sa.Column("resource_type", sa.String(length=160), nullable=False),
        sa.Column("retention_days", sa.Integer(), nullable=False),
        sa.Column("archive_after_days", sa.Integer(), nullable=True),
        sa.Column("delete_after_days", sa.Integer(), nullable=True),
        sa.Column("legal_hold", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["access_organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "resource_type", name="uq_retention_policy_scope_resource"),
    )
    op.create_index("ix_retention_policies_organization_id", "retention_policies", ["organization_id"])
    op.create_index("ix_retention_policies_resource_type", "retention_policies", ["resource_type"])


def _drop_governance_tables() -> None:
    op.drop_index("ix_retention_policies_resource_type", table_name="retention_policies")
    op.drop_index("ix_retention_policies_organization_id", table_name="retention_policies")
    op.drop_table("retention_policies")
    op.drop_index("ix_system_limits_key", table_name="system_limits")
    op.drop_index("ix_system_limits_organization_id", table_name="system_limits")
    op.drop_table("system_limits")
    op.drop_index("ix_secret_grants_grantee_id", table_name="secret_grants")
    op.drop_index("ix_secret_grants_grantee_type", table_name="secret_grants")
    op.drop_index("ix_secret_grants_secret_id", table_name="secret_grants")
    op.drop_table("secret_grants")
    op.drop_index("ix_secret_versions_secret_id", table_name="secret_versions")
    op.drop_table("secret_versions")
    op.drop_index("ix_secrets_current_version_id", table_name="secrets")
    op.drop_index("ix_secrets_status", table_name="secrets")
    op.drop_index("ix_secrets_key", table_name="secrets")
    op.drop_index("ix_secrets_organization_id", table_name="secrets")
    op.drop_table("secrets")


def _seed_role_permissions() -> None:
    manager = ",".join(f"'{item}'" for item in PERMISSIONS if not item.startswith("admin.") and item != "secret.manage")
    operator = ",".join(
        f"'{item}'"
        for item in (
            "automation.read",
            "execution.read",
            "execution.create",
            "execution.cancel",
            "flow.read",
            "flow.execute",
            "schedule.read",
            "schedule.trigger",
            "artifact.read",
            "artifact.download",
            "agent.read",
        )
    )
    viewer = ",".join(
        f"'{item}'"
        for item in (
            "automation.read",
            "execution.read",
            "flow.read",
            "schedule.read",
            "artifact.read",
            "agent.read",
        )
    )
    for role_slug, permission_list in (("manager", manager), ("operator", operator), ("viewer", viewer)):
        op.execute(
            f"""
            INSERT INTO role_permissions (role_id, permission_key)
            SELECT roles.id, permissions.key
            FROM roles
            JOIN permissions ON permissions.key IN ({permission_list})
            WHERE roles.slug = '{role_slug}'
            ON CONFLICT ON CONSTRAINT uq_role_permissions_role_permission DO NOTHING
            """
        )


def _seed_governance_defaults() -> None:
    system_limits = sa.table(
        "system_limits",
        sa.column("key", sa.String),
        sa.column("value", sa.Integer),
        sa.column("unit", sa.String),
        sa.column("description", sa.Text),
        sa.column("metadata", JSONB),
    )
    op.bulk_insert(
        system_limits,
        [
            {"key": "package.max_size_mb", "value": 200, "unit": "mb", "description": "Maximum automation package upload size.", "metadata": {}},
            {"key": "artifact.max_size_mb", "value": 200, "unit": "mb", "description": "Maximum individual artifact size.", "metadata": {}},
            {"key": "agent.max_registered", "value": 100, "unit": "count", "description": "Maximum registered agents.", "metadata": {}},
            {"key": "execution.max_concurrent", "value": 20, "unit": "count", "description": "Maximum concurrent executions.", "metadata": {}},
            {"key": "schedule.min_interval_seconds", "value": 60, "unit": "seconds", "description": "Minimum recurring schedule interval.", "metadata": {}},
            {"key": "flow.max_nodes", "value": 100, "unit": "count", "description": "Maximum nodes in a flow.", "metadata": {}},
            {"key": "execution.max_timeout_seconds", "value": 14400, "unit": "seconds", "description": "Maximum execution timeout.", "metadata": {}},
            {"key": "execution.max_retries", "value": 3, "unit": "count", "description": "Maximum retry attempts.", "metadata": {}},
            {"key": "realtime.max_sse_connections", "value": 250, "unit": "count", "description": "Maximum SSE connections.", "metadata": {}},
            {"key": "gateway.max_message_bytes", "value": 65536, "unit": "bytes", "description": "Maximum gateway message size.", "metadata": {}},
        ],
    )

    retention = sa.table(
        "retention_policies",
        sa.column("resource_type", sa.String),
        sa.column("retention_days", sa.Integer),
        sa.column("archive_after_days", sa.Integer),
        sa.column("delete_after_days", sa.Integer),
        sa.column("legal_hold", sa.Boolean),
        sa.column("enabled", sa.Boolean),
    )
    op.bulk_insert(
        retention,
        [
            {"resource_type": "ExecutionEvent", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 180, "legal_hold": False, "enabled": True},
            {"resource_type": "ExecutionLog", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
            {"resource_type": "ExecutionMetric", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 180, "legal_hold": False, "enabled": True},
            {"resource_type": "Artifact", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 365, "legal_hold": False, "enabled": True},
            {"resource_type": "AgentResourceSnapshot", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
            {"resource_type": "AuditEvent", "retention_days": 365, "archive_after_days": None, "delete_after_days": None, "legal_hold": True, "enabled": True},
            {"resource_type": "InboxMessage", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
            {"resource_type": "OutboxMessage", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
            {"resource_type": "AgentCommand", "retention_days": 90, "archive_after_days": 30, "delete_after_days": 180, "legal_hold": False, "enabled": True},
            {"resource_type": "Diagnostic", "retention_days": 30, "archive_after_days": 15, "delete_after_days": 90, "legal_hold": False, "enabled": True},
        ],
    )

