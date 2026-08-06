"""Database URL normalization for deployment environments.

Render Postgres exposes a standard ``postgres://``/``postgresql://``
connection string. SQLAlchemy needs the explicit psycopg v3 dialect when
this project uses ``psycopg[binary]`` rather than psycopg2.
"""


def normalize_database_url(url: str) -> str:
    """Return a SQLAlchemy URL compatible with psycopg v3.

    SQLite and already-explicit SQLAlchemy dialect URLs are returned
    unchanged.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url
