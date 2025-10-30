import os
import sys
from logging.config import fileConfig

from alembic import context

# Note: Unlike the standard Alembic template, we do not import `engine_from_config` or `pool` from SQLAlchemy.
# Instead, `run_migrations_online` creates its own engine using `create_engine` directly.
# This is intentional and avoids unused imports.

# Add project root so backend.* imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.core.config import settings  # noqa
from backend.core.db import Base  # noqa

# Import all models so they're registered with Base
from backend.models.meetings import *  # noqa
from backend.models.integrations import *  # noqa
from backend.models.tasks import *  # noqa

# Explicit RBAC model imports for better namespace control
from backend.database.models.rbac import DBRole, DBUser, Organization, UserRole  # noqa

# Ensure models are registered with Base.metadata for alembic auto-generation
_rbac_models = [DBRole, DBUser, Organization, UserRole]
assert all(
    hasattr(model, "__tablename__") for model in _rbac_models
), "RBAC models must be loaded"

config = context.config
if (
    not config.get_main_option("sqlalchemy.url")
    or config.get_main_option("sqlalchemy.url") == "sqlite:///"
):
    if not settings.sqlalchemy_url:
        raise ValueError(
            "No sqlalchemy.url configured in alembic.ini or environment variables. "
            "Please set DATABASE_URL or configure sqlalchemy.url in alembic.ini."
        )
    config.set_main_option("sqlalchemy.url", settings.sqlalchemy_url)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    # Create a fresh engine for migrations (don't use LazyProxy)
    from sqlalchemy import create_engine

    url = config.get_main_option("sqlalchemy.url")
    # URL is guaranteed to be set by the validation above
    assert url is not None  # For type checker - validation above ensures this
    connectable = create_engine(url)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

    connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
