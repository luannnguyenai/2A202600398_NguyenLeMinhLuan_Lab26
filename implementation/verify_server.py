from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from starlette.testclient import TestClient

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from implementation.auth import auth_middleware
from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


DB_PATH = Path(__file__).with_name("lab.sqlite")


def _print_step(name: str, value: Any) -> None:
    print(f"\n## {name}")
    print(json.dumps(value, indent=2, default=str))


def verify_database_layer() -> None:
    create_database(DB_PATH)
    adapter = SQLiteAdapter(DB_PATH)

    _print_step("tables", adapter.list_tables())
    _print_step(
        "valid search",
        adapter.search(
            "students",
            filters=[{"column": "cohort", "operator": "=", "value": "A1"}],
            columns=["name", "cohort", "score"],
            order_by="score",
            descending=True,
            limit=2,
        ),
    )
    _print_step("valid insert", adapter.insert("students", {"name": "Nora Lee", "cohort": "C3", "score": 90.0}))
    _print_step("valid aggregate", adapter.aggregate("students", "avg", column="score", group_by="cohort"))
    _print_step("schema resource payload", adapter.database_schema())

    try:
        adapter.search("missing_table")
    except ValidationError as exc:
        _print_step("invalid request error", {"error": str(exc)})
    else:
        raise AssertionError("invalid table search did not raise ValidationError")


async def verify_mcp_layer() -> None:
    try:
        from fastmcp import Client
    except ImportError as exc:
        raise RuntimeError("FastMCP is not installed. Run `python3 -m pip install -r requirements.txt`.") from exc

    from implementation.mcp_server import mcp

    async with Client(mcp) as client:
        tools = await client.list_tools()
        tool_names = sorted(tool.name for tool in tools)
        _print_step("mcp tools", tool_names)
        assert tool_names == ["aggregate", "insert", "search"]

        resources = await client.list_resources()
        resource_uris = sorted(str(resource.uri) for resource in resources)
        _print_step("mcp resources", resource_uris)
        assert "schema://database" in resource_uris

        templates = await client.list_resource_templates()
        template_uris = sorted(str(template.uriTemplate) for template in templates)
        _print_step("mcp resource templates", template_uris)
        assert "schema://table/{table_name}" in template_uris

        result = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": [{"column": "cohort", "operator": "=", "value": "A1"}],
                "columns": ["name", "cohort"],
                "limit": 1,
            },
        )
        _print_step("mcp valid tool call", result.data)

        schema = await client.read_resource("schema://table/students")
        _print_step("mcp schema read", schema[0].text)

        invalid = await client.call_tool("search", {"table": "missing"})
        _print_step("mcp invalid tool call", invalid.data)
        assert invalid.data == {"ok": False, "error": "Unknown table: missing"}


def verify_http_auth_layer() -> None:
    from implementation.mcp_server import mcp

    app = mcp.http_app(
        path="/mcp",
        middleware=auth_middleware("demo-token"),
        transport="http",
        stateless_http=True,
    )
    client = TestClient(app)

    missing = client.get("/mcp")
    wrong = client.get("/mcp", headers={"Authorization": "Bearer wrong"})
    allowed = client.get("/mcp", headers={"Authorization": "Bearer demo-token"})

    auth_demo = {
        "missing_token_status": missing.status_code,
        "missing_token_body": missing.json(),
        "wrong_token_status": wrong.status_code,
        "wrong_token_body": wrong.json(),
        "valid_token_status": allowed.status_code,
        "valid_token_body": allowed.text,
    }
    _print_step("http bearer auth demo", auth_demo)
    assert missing.status_code == 401
    assert wrong.status_code == 403
    assert allowed.status_code == 405


def main() -> None:
    verify_database_layer()
    asyncio.run(verify_mcp_layer())
    verify_http_auth_layer()
    print("\nVerification completed.")


if __name__ == "__main__":
    main()
