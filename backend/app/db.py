"""Database access. The business logic is plain SQL (as in the desktop app, which keeps the two
versions easy to compare); `Db` is a thin wrapper that gives it dict rows and `?` placeholders."""
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Cursor:
    def __init__(self, result):
        self._r = result
        self.rowcount = result.rowcount

    def fetchone(self):
        row = self._r.mappings().fetchone() if self._r.returns_rows else None
        return dict(row) if row else None

    def fetchall(self):
        return [dict(r) for r in self._r.mappings().fetchall()] if self._r.returns_rows else []

    def __iter__(self):
        return iter(self.fetchall())


class Db:
    def __init__(self, session: Session):
        self.session = session

    def execute(self, sql, params=()):
        # psycopg uses %s; a literal % in the SQL (never used here) would have to be doubled
        return Cursor(self.session.connection().exec_driver_sql(sql.replace("?", "%s"), tuple(params)))

    def insert(self, sql, params=()):
        """INSERT ... returning the new id."""
        return self.execute(sql + " RETURNING id", params).fetchone()["id"]

    def lock_user(self, user_id):
        """Serialise the writes of one user (a double click must not run twice in parallel);
        released at commit/rollback."""
        self.execute("SELECT pg_advisory_xact_lock(?)", (user_id,))

    def commit(self):
        self.session.commit()

    def rollback(self):
        self.session.rollback()


def get_db():
    session = SessionLocal()
    try:
        yield Db(session)
    finally:
        session.rollback()      # anything not committed is dropped
        session.close()
