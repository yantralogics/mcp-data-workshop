"""Tests for the final server, using FastMCP's in-memory client.

Passing the server object (not a path) to Client() connects in-process:
no subprocess, no network. It's the fastest way to test an MCP server.

    pytest -q
"""

import sys
from pathlib import Path

import pytest
from fastmcp import Client

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "steps"))
from step_d_prompt import mcp  # noqa: E402


@pytest.fixture
async def client():
    async with Client(mcp) as c:
        yield c


async def test_discovery(client):
    tools = {t.name for t in await client.list_tools()}
    assert {"list_tables", "run_query"} <= tools
    prompts = {p.name for p in await client.list_prompts()}
    assert {"analyze_table", "kpi_summary"} <= prompts


async def test_list_tables(client):
    result = await client.call_tool("list_tables", {})
    tables = {row["table"]: row["rows"] for row in result.data}
    assert tables["customers"] == 300
    assert tables["orders"] == 2500


async def test_schema_resource(client):
    contents = await client.read_resource("schema://orders")
    assert "order_date" in contents[0].text


async def test_unknown_table_resource(client):
    with pytest.raises(Exception, match="Unknown table"):
        await client.read_resource("schema://nope")


async def test_select_works_and_caps_rows(client):
    result = await client.call_tool("run_query", {"sql": "SELECT * FROM orders", "max_rows": 5})
    assert result.data["row_count"] == 5
    assert result.data["truncated"] is True
    assert result.data["columns"][0] == "order_id"


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM orders",
        "SELECT 1; DROP TABLE orders",
        "PRAGMA writable_schema=1",
    ],
)
async def test_writes_are_rejected(client, sql):
    result = await client.call_tool("run_query", {"sql": sql}, raise_on_error=False)
    assert result.is_error


async def test_readonly_connection_blocks_sneaky_writes(client):
    # Passes the keyword check (starts with WITH) but tries to write.
    # The read-only connection is the real guarantee.
    sql = "WITH x AS (SELECT 1) INSERT INTO products VALUES (999, 'x', 'x', 1)"
    result = await client.call_tool("run_query", {"sql": sql}, raise_on_error=False)
    assert result.is_error


async def test_bad_sql_returns_helpful_error(client):
    result = await client.call_tool("run_query", {"sql": "SELECT nope FROM orders"},
                                    raise_on_error=False)
    assert result.is_error and "no such column" in result.content[0].text


async def test_max_rows_validated_by_schema(client):
    result = await client.call_tool("run_query", {"sql": "SELECT 1", "max_rows": 10_000},
                                    raise_on_error=False)
    assert result.is_error


async def test_prompt_renders(client):
    p = await client.get_prompt("analyze_table", {"table": "customers", "focus": "segments"})
    assert "schema://customers" in p.messages[0].content.text
