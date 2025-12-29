import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.config import settings

# Create ./data folder if using default sqlite path
if settings.database_url.startswith("sqlite:///./"):
    # Extract relative path portion after sqlite:///./
    rel_path = settings.database_url.replace("sqlite:///./", "", 1)
    folder = os.path.dirname(rel_path)
    if folder:
        os.makedirs(folder, exist_ok=True)

engine: Engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
    """Enable SQLite foreign keys (best-effort)."""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
    except Exception:
        # If not SQLite or driver doesn't support, ignore.
        pass


SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# PUBLIC_INTERFACE
def init_db() -> None:
    """Initialize database tables (create if missing).

    Also performs a lightweight best-effort migration for SQLite by adding new columns
    if they are missing (this project intentionally avoids full migration tooling).
    """
    from sqlalchemy import inspect, text

    from src.models import Base  # local import to avoid import cycles

    Base.metadata.create_all(bind=engine)

    # Best-effort schema migration for SQLite: add new Game columns if missing.
    if engine.url.get_backend_name() == "sqlite":
        inspector = inspect(engine)
        try:
            cols = {c["name"] for c in inspector.get_columns("games")}
        except Exception:
            cols = set()

        alter_stmts = []
        if "mode" not in cols:
            alter_stmts.append("ALTER TABLE games ADD COLUMN mode VARCHAR(8) DEFAULT 'pvp'")
        if "ai_side" not in cols:
            alter_stmts.append("ALTER TABLE games ADD COLUMN ai_side VARCHAR(8)")
        if "ai_level" not in cols:
            alter_stmts.append("ALTER TABLE games ADD COLUMN ai_level INTEGER DEFAULT 1")

        if alter_stmts:
            with engine.begin() as conn:
                for stmt in alter_stmts:
                    conn.execute(text(stmt))


# PUBLIC_INTERFACE
def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency to provide a SQLAlchemy session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context manager for non-FastAPI usage (scripts, etc.)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
