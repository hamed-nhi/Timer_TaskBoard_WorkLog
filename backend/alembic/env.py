from alembic import context
from sqlalchemy import create_engine

from app.config import settings
from app.models import Base

target_metadata = Base.metadata


def apply_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    supplied = context.config.attributes.get("connection")
    if supplied is not None:
        apply_migrations(supplied)
        return
    # tests pass their own url through the alembic config attributes
    engine = create_engine(context.config.attributes.get("url") or settings.database_url)
    with engine.connect() as connection:
        apply_migrations(connection)


run_migrations_online()
