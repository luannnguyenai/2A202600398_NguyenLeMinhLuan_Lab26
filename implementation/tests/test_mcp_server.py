import pytest
from fastmcp import Client

from implementation.mcp_server import mcp


@pytest.mark.anyio
async def test_mcp_discovers_required_tools_and_resources():
    async with Client(mcp) as client:
        tools = await client.list_tools()
        resources = await client.list_resources()
        templates = await client.list_resource_templates()

    assert sorted(tool.name for tool in tools) == ["aggregate", "insert", "search"]
    assert "schema://database" in [str(resource.uri) for resource in resources]
    assert "schema://table/{table_name}" in [
        str(template.uriTemplate) for template in templates
    ]


@pytest.mark.anyio
async def test_mcp_invalid_tool_call_returns_clear_error_payload():
    async with Client(mcp) as client:
        result = await client.call_tool("search", {"table": "missing"})

    assert result.data == {"ok": False, "error": "Unknown table: missing"}
