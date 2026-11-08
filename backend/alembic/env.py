from logging.config import fileConfig
import os
import sys
from alembic import context
from sqlalchemy import create_engine

# Add the project root to sys.path so imports work
config_file_path = context.config.config_file_name
project_root = os.path.abspath(os.path.join(config_file_path, "..", ".."))
sys.path.append(project_root)

# Import Base metadata
from backend.app.models import Base  # noqa: E402

target_metadata = Base.metadata

# Interpret the config file for Python logging.
if config_file_path is not None:
    fileConfig(config_file_path)

# Get the database URL from alembic.ini (you will replace with env vars later)
url = context.get_x_argument(as_dictionary=True).get('url')
if not url:
    url = context.config.get_main_option('sqlalchemy.url')


def run_migrations_offline():
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = create_engine(url, poolclass=None)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

