"""webhook_secret_security"""

from __future__ import annotations

import hashlib

from alembic import op
import sqlalchemy as sa

revision = "b6c7d8e9f001"
down_revision = "5a6b7c8d9e0f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("triggers", sa.Column("name", sa.String(length=120), nullable=True))
    op.add_column("triggers", sa.Column("secret_hash", sa.String(length=64), nullable=True))
    op.add_column("triggers", sa.Column("secret_last_four", sa.String(length=16), nullable=True))
    op.add_column("triggers", sa.Column("secret_created_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("triggers", sa.Column("secret_rotated_at", sa.DateTime(timezone=True), nullable=True))

    bind = op.get_bind()
    rows = bind.execute(sa.text("select id, route_path, secret_token, created_at from triggers")).mappings().all()
    for row in rows:
        secret = row["secret_token"] or ""
        bind.execute(
            sa.text(
                """
                update triggers
                   set name = coalesce(name, :name),
                       secret_hash = :secret_hash,
                       secret_last_four = :secret_last_four,
                       secret_created_at = coalesce(secret_created_at, :created_at),
                       secret_token = :placeholder
                 where id = :trigger_id
                """
            ),
            {
                "trigger_id": row["id"],
                "name": row["route_path"],
                "secret_hash": hashlib.sha256(f":{secret}".encode("utf-8")).hexdigest() if secret else None,
                "secret_last_four": secret[-4:] if secret else None,
                "created_at": row["created_at"],
                "placeholder": "__redacted__",
            },
        )


def downgrade() -> None:
    op.drop_column("triggers", "secret_rotated_at")
    op.drop_column("triggers", "secret_created_at")
    op.drop_column("triggers", "secret_last_four")
    op.drop_column("triggers", "secret_hash")
    op.drop_column("triggers", "name")
