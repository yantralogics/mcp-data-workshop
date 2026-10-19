"""Checkpoint A: the smallest useful MCP server.

Concepts:
  * A FastMCP instance is the server.
  * @mcp.tool turns a plain Python function into an MCP tool.
  * The docstring becomes the tool description (what the MODEL reads).
  * Type hints become the JSON Schema for the tool's input.
  * mcp.run() defaults to the stdio transport: the host launches this file
    as a subprocess and talks JSON-RPC over stdin/stdout.

Try it:
    fastmcp list steps/step_a_hello.py --input-schema
    fastmcp call steps/step_a_hello.py greet name=Ada
    fastmcp dev inspector steps/step_a_hello.py
"""

from fastmcp import FastMCP

mcp = FastMCP("sales-data")


@mcp.tool
def greet(name: str) -> str:
    """Say hello to someone. Use this to confirm the server is connected."""
    return f"Hello, {name}! The sales-data MCP server is up."


@mcp.tool
def days_between(start: str, end: str) -> int:
    """Count the days between two ISO dates (YYYY-MM-DD).

    Example: days_between("2026-01-01", "2026-03-01") -> 59
    """
    from datetime import date

    return (date.fromisoformat(end) - date.fromisoformat(start)).days


if __name__ == "__main__":
    mcp.run()  # stdio transport by default
