import os
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker


def database_url() -> str:
    url = os.environ["DATABASE_URL"]
    # .env uses the libpq form; SQLAlchemy needs the driver name for psycopg 3.
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


_engine: Engine | None = None
_session_factory: sessionmaker[Session] | None = None


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(database_url(), pool_pre_ping=True)
    return _engine


def _reset_after_fork() -> None:
    # RQ forks a work-horse per job; the child must not reuse the parent's pooled connections
    # (shared socket -> psycopg prepared-statement clashes, broken transactions).
    if _engine is not None:
        _engine.dispose(close=False)


os.register_at_fork(after_in_child=_reset_after_fork)


def session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(engine(), expire_on_commit=False)
    return _session_factory


@contextmanager
def session_scope() -> Iterator[Session]:
    session = session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
