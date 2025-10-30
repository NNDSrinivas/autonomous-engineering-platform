import os
import sys
from logging.config import fileConfig

from alembic import context

# Add project root so backend.* imports work
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from backend.core.config import settings  # noqa
from backend.core.db import Base  # noqa

# Import all models so they're registered with Base
from backend.models.meetings import *  # noqa
from backend.models.integrations import *  # noqa
from backend.models.tasks import *  # noqa

config = context.config
if (
    not config.get_main_option("sqlalchemy.url")
    or config.get_main_option("sqlalchemy.url") == "sqlite:///"
):
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
