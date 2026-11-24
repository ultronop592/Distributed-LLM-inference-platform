import os
import time

from sqlalchemy import (
    BigInteger,
    Column,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    func,
    insert,
    select,
    update,
)

metadata = MetaData()

api_keys = Table(
    "api_keys",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(64), nullable=False),
    Column("key_hash", String(64), nullable=False, unique=True),
    Column("prefix", String(16), nullable=False),
    Column("created_at", BigInteger, nullable=False),
    Column("revoked_at", BigInteger, nullable=True),
)

usage = Table(
    "usage",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("key_id", Integer, ForeignKey("api_keys.id"), nullable=False),
    Column("prompt_tokens", Integer, nullable=False),
    Column("completion_tokens", Integer, nullable=False),
    Column("created_at", BigInteger, nullable=False),
    Index("ix_usage_key_id", "key_id"),
)

_engines = {}


def database_url():
    url = os.getenv("DATABASE_URL", "sqlite:///gateway.db")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


def get_engine():
    url = database_url()
    engine = _engines.get(url)
    if engine is None:
        if url.startswith("sqlite"):
            engine = create_engine(url, connect_args={"check_same_thread": False})
        else:
            engine = create_engine(
                url,
                pool_pre_ping=True,
                pool_size=5,
                max_overflow=5,
                pool_recycle=300,
                connect_args={"connect_timeout": 15},
            )
        _engines[url] = engine
    return engine


def init_db():
    engine = get_engine()
    if engine.dialect.name == "sqlite":
        metadata.create_all(engine)


def insert_key(name, key_hash, prefix):
    statement = insert(api_keys).values(
        name=name, key_hash=key_hash, prefix=prefix, created_at=int(time.time())
    )
    with get_engine().begin() as conn:
        return conn.execute(statement).inserted_primary_key[0]


def get_active_by_hash(key_hash):
    statement = select(api_keys.c.id, api_keys.c.name).where(
        api_keys.c.key_hash == key_hash, api_keys.c.revoked_at.is_(None)
    )
    with get_engine().connect() as conn:
        row = conn.execute(statement).first()
    return dict(row._mapping) if row else None


def list_keys():
    statement = select(
        api_keys.c.id,
        api_keys.c.name,
        api_keys.c.prefix,
        api_keys.c.created_at,
        api_keys.c.revoked_at,
    ).order_by(api_keys.c.id)
    with get_engine().connect() as conn:
        return [dict(row._mapping) for row in conn.execute(statement)]


def revoke_key(key_id):
    statement = (
        update(api_keys)
        .where(api_keys.c.id == key_id, api_keys.c.revoked_at.is_(None))
        .values(revoked_at=int(time.time()))
    )
    with get_engine().begin() as conn:
        return conn.execute(statement).rowcount > 0


def record_usage(key_id, prompt_tokens, completion_tokens):
    statement = insert(usage).values(
        key_id=key_id,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        created_at=int(time.time()),
    )
    with get_engine().begin() as conn:
        conn.execute(statement)


def usage_summary():
    statement = (
        select(
            api_keys.c.id,
            api_keys.c.name,
            api_keys.c.prefix,
            func.count(usage.c.id).label("requests"),
            func.coalesce(func.sum(usage.c.prompt_tokens), 0).label("prompt_tokens"),
            func.coalesce(func.sum(usage.c.completion_tokens), 0).label("completion_tokens"),
        )
        .select_from(api_keys.outerjoin(usage, usage.c.key_id == api_keys.c.id))
        .group_by(api_keys.c.id, api_keys.c.name, api_keys.c.prefix)
        .order_by(api_keys.c.id)
    )
    with get_engine().connect() as conn:
        rows = conn.execute(statement).all()
    return [
        {
            "id": row.id,
            "name": row.name,
            "prefix": row.prefix,
            "requests": int(row.requests),
            "prompt_tokens": int(row.prompt_tokens),
            "completion_tokens": int(row.completion_tokens),
        }
        for row in rows
    ]