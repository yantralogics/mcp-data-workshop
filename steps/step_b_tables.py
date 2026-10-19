"""Checkpoint B: tools vs. resources, against a real SQLite database.

New concepts:
  * A TOOL is something the model decides to call (list_tables).
  * A RESOURCE is read-only context addressed by a URI. The application
    (or the user) decides to load it; it's like a GET endpoint.
  * A resource TEMPLATE has a placeholder ({table}) so one function serves
    many URIs: schema://customers, schema://orders, ...
  * Resolve file paths from __file__, never from the current directory:
    the host app launches your server from wherever it likes.

Try it:
    fastmcp list steps/step_b_tables.py --resources   # templates are listed separately; see client_demo.py
    fastmcp call steps/step_b_tables.py list_tables
    fastmcp call steps/step_b_tables.py schema://orders
"""

import sqlite3
from pathlib import Path

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sales.db"

mcp = FastMCP(
    "sales-data",
    instructions="Read-only access to the Blue Ridge Outfitters sales database (SQLite).",
)


def connect() -> sqlite3.Connection:
    """Open the database read-only. The OS-level guarantee beats any string check."""
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


def table_names(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


@mcp.tool(annotations={"readOnlyHint": True})
def list_tables() -> list[dict]:
    """List every table in the sales database with its row count.

    Call this first to discover what data is available before writing a query.
    """
    with connect() as con:
        return [
            {"table": t, "rows": con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]}
            for t in table_names(con)
        ]


@mcp.resource("schema://{table}", mime_type="text/plain")
def table_schema(table: str) -> str:
    """Column names, types and the CREATE statement for one table."""
    with connect() as con:
        if table not in table_names(con):  # whitelist: never interpolate unchecked input
            raise ResourceError(f"Unknown table '{table}'. Known: {', '.join(table_names(con))}")
        ddl = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    lines = [f"{c[1]} {c[2]}" for c in cols]
    return f"Table: {table}\nColumns:\n  " + "\n  ".join(lines) + f"\n\nDDL:\n{ddl}"


if __name__ == "__main__":
    mcp.run()
