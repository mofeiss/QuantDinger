from unittest.mock import MagicMock

from app.utils import db_postgres


def test_postgres_pool_uses_shanghai_timezone_by_default(monkeypatch):
    captured = {}

    class FakeThreadedConnectionPool:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(db_postgres, "_connection_pool", None)
    monkeypatch.setattr(db_postgres, "HAS_PSYCOPG2", True)
    monkeypatch.setattr(db_postgres.pool, "ThreadedConnectionPool", FakeThreadedConnectionPool)
    monkeypatch.setattr(db_postgres, "_get_database_url", lambda: "postgresql://u:p@localhost:5432/quantdinger")
    monkeypatch.setattr(db_postgres, "DB_TIMEZONE", "Asia/Shanghai")

    db_postgres._get_connection_pool()

    assert captured["options"] == "-c timezone=Asia/Shanghai"


def test_postgres_pool_timezone_can_be_overridden(monkeypatch):
    captured = {}

    class FakeThreadedConnectionPool:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(db_postgres, "_connection_pool", None)
    monkeypatch.setattr(db_postgres, "HAS_PSYCOPG2", True)
    monkeypatch.setattr(db_postgres.pool, "ThreadedConnectionPool", FakeThreadedConnectionPool)
    monkeypatch.setattr(db_postgres, "_get_database_url", lambda: "postgresql://u:p@localhost:5432/quantdinger")
    monkeypatch.setattr(db_postgres, "DB_TIMEZONE", "UTC")

    db_postgres._get_connection_pool()

    assert captured["options"] == "-c timezone=UTC"
