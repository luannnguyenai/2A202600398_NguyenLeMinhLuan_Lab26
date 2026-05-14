from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from fastmcp import FastMCP
except ImportError as exc:  # pragma: no cover - exercised by setup verification
    raise SystemExit(
        "FastMCP is not installed. Run `python3 -m pip install -r requirements.txt` first."
    ) from exc

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from implementation.auth import auth_middleware
from implementation.db import DatabaseAdapter, ValidationError, create_adapter
from implementation.init_db import DEFAULT_DB_PATH, create_database


DB_PATH = Path(__file__).with_name("lab.sqlite")


def build_adapter_from_env() -> DatabaseAdapter:
    backend = os.environ.get("MCP_DB_BACKEND", "sqlite").lower()
    if backend == "sqlite":
        configured_path = Path(os.environ.get("MCP_SQLITE_PATH", str(DB_PATH)))
        if not configured_path.exists():
            create_database(configured_path)
        return create_adapter("sqlite", db_path=str(configured_path))
    if backend in {"postgres", "postgresql"}:
        dsn = os.environ.get("DATABASE_URL") or os.environ.get("MCP_POSTGRES_DSN")
        if not dsn:
            raise SystemExit("PostgreSQL mode requires DATABASE_URL or MCP_POSTGRES_DSN.")
        return create_adapter("postgresql", dsn=dsn)
    raise SystemExit(f"Unsupported MCP_DB_BACKEND: {backend}")


adapter = build_adapter_from_env()
mcp = FastMCP("SQLite Lab MCP Server")


@mcp.tool(name="search")
def search(
    table: str,
    filters: Optional[List[Dict[str, Any]]] = None,
    columns: Optional[List[str]] = None,
    limit: int = 20,
    offset: int = 0,
    order_by: Optional[str] = None,
    descending: bool = False,
) -> Dict[str, Any]:
    """Search rows with validated filters, ordering, limit, and offset."""
    try:
        return adapter.search(table, filters, columns, limit, offset, order_by, descending)
    except ValidationError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="insert")
def insert(table: str, values: Dict[str, Any]) -> Dict[str, Any]:
    """Insert one row into a known table and return the inserted payload."""
    try:
        return adapter.insert(table, values)
    except ValidationError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: Optional[str] = None,
    filters: Optional[List[Dict[str, Any]]] = None,
    group_by: Optional[str] = None,
) -> Dict[str, Any]:
    """Run count, avg, sum, min, or max with optional filters and grouping."""
    try:
        return adapter.aggregate(table, metric, column, filters, group_by)
    except ValidationError as exc:
        return {"ok": False, "error": str(exc)}


@mcp.resource("schema://database")
def database_schema() -> str:
    """Return the full SQLite schema as JSON."""
    return json.dumps(adapter.database_schema(), indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Return a single table schema as JSON."""
    return json.dumps(adapter.table_schema(table_name), indent=2)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the SQLite Lab FastMCP server.")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
    )
    parser.add_argument("--host", default=os.environ.get("MCP_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("MCP_PORT", "8000")))
    parser.add_argument("--path", default=os.environ.get("MCP_PATH"))
    parser.add_argument(
        "--auth-token",
        default=os.environ.get("MCP_AUTH_TOKEN"),
        help="Bearer token required for HTTP, streamable-http, or SSE transports.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    if DEFAULT_DB_PATH != DB_PATH and not DEFAULT_DB_PATH.exists():
        create_database(DEFAULT_DB_PATH)
    args = parse_args()
    if args.transport == "stdio":
        mcp.run()
    else:
        kwargs: Dict[str, Any] = {
            "host": args.host,
            "port": args.port,
            "middleware": auth_middleware(args.auth_token),
        }
        if args.path:
            kwargs["path"] = args.path
        mcp.run(args.transport, **kwargs)
