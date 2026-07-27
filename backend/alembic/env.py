from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.core.config import get_settings
from app.core.database import Base
from app.models import (
    audit,
    automation,
    automation_source,
    automation_version,
    category,
    execution,
    github_integration,
    job,
    log,
    role,
    schedule,
    trigger,
    user,
    user_category_permission,
    worker,
)
from modules.catalog.infrastructure.orm import models as catalog_models
from modules.dispatch.infrastructure.orm import models as dispatch_models
from modules.fleet.infrastructure.orm import models as fleet_models
from modules.orchestration.infrastructure.orm import models as orchestration_models
from modules.governance.infrastructure.orm import models as governance_models
from modules.shared.infrastructure.orm import models as shared_models
from modules.storage.infrastructure.orm import models as storage_models
from modules.telemetry.infrastructure.orm import models as telemetry_models

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.database_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
