from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

DATABASE_URL = settings.DATABASE_URL

# SQLite needs check_same_thread=False (single-file, thread-safety workaround).
# Postgres (and other real DB servers) don't understand that argument at all —
# passing it would crash the connection. So the connect_args are conditional
# on which database we're actually pointed at.
if DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
    )

    # SQLite does NOT enforce foreign key constraints by default (unlike
    # every other real database), so ON DELETE CASCADE defined on the
    # models silently does nothing unless this is turned on per-connection.
    # Without this, deleting a school locally would leave orphaned users/
    # students/fees behind — while the same delete on production (Postgres)
    # correctly cascades. This keeps local dev behavior matching production.
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
else:
    # Serverless platforms (e.g. Vercel) spin up short-lived function
    # instances — NullPool avoids leaking idle connections across
    # invocations, which matters a lot on free-tier Postgres connection
    # limits (Supabase/Neon free tiers cap concurrent connections).
    from sqlalchemy.pool import NullPool

    # ✅ CRITICAL: Disable psycopg prepared statement caching.
    # Supabase uses PgBouncer in transaction mode. psycopg3 by default
    # prepares statements after 5 uses and caches them per-connection.
    # When PgBouncer reuses a connection across different clients, the
    # cached statement name (e.g. "_pg3_0") collides → "DuplicatePreparedStatement".
    # prepare_threshold=None disables this caching entirely → fixes it.
    _pg_connect_args = {}
    if DATABASE_URL.startswith("postgresql"):
        _pg_connect_args["prepare_threshold"] = None

    engine = create_engine(
        DATABASE_URL,
        poolclass=NullPool,
        connect_args=_pg_connect_args,
        echo=False,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)