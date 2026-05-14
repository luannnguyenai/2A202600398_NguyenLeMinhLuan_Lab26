from starlette.testclient import TestClient

from implementation.auth import auth_middleware
from implementation.db import DatabaseAdapter, PostgreSQLAdapter, SQLiteAdapter, create_adapter
from implementation.init_db import create_database
from implementation.mcp_server import mcp


def test_http_bearer_auth_middleware_blocks_missing_or_wrong_token():
    app = mcp.http_app(
        path="/mcp",
        middleware=auth_middleware("secret-token"),
        transport="http",
        stateless_http=True,
    )
    client = TestClient(app)

    missing = client.get("/mcp")
    wrong = client.get("/mcp", headers={"Authorization": "Bearer wrong"})
    allowed = client.get("/mcp", headers={"Authorization": "Bearer secret-token"})

    assert missing.status_code == 401
    assert missing.json() == {"ok": False, "error": "Missing bearer token"}
    assert wrong.status_code == 403
    assert wrong.json() == {"ok": False, "error": "Invalid bearer token"}
    assert allowed.status_code == 405
    assert "Method Not Allowed" in allowed.text


def test_adapter_factory_returns_sqlite_and_postgres_adapters(tmp_path):
    db_path = create_database(tmp_path / "lab.sqlite")

    sqlite_adapter = create_adapter("sqlite", db_path=str(db_path))
    postgres_adapter = create_adapter("postgresql", dsn="postgresql://user:pass@localhost/db")

    assert isinstance(sqlite_adapter, SQLiteAdapter)
    assert isinstance(sqlite_adapter, DatabaseAdapter)
    assert isinstance(postgres_adapter, PostgreSQLAdapter)
    assert isinstance(postgres_adapter, DatabaseAdapter)
    assert postgres_adapter.dsn == "postgresql://user:pass@localhost/db"
