"""Checkpoint C: let the model query the data, safely.

New concepts:
  * Guardrails live in the server, not in the prompt. Three layers here:
      1. the connection is opened read-only (mode=ro): writes are impossible
      2. only a single SELECT/WITH statement is accepted (good error messages)
      3. results are capped (max_rows) so you never flood the model's context
  * Annotated[..., Field(...)] adds constraints + descriptions to the schema.
    The host validates arguments before your code even runs.
  * Return structured data (a dict). FastMCP sends it as structured content
    AND as text, so both the model and programmatic clients can use it.
  * Raise ToolError for problems the model can fix (bad SQL, wrong column).
    The message goes back to the model, which usually retries correctly.

Try it:
    fastmcp call steps/step_c_query.py run_query \
        sql="SELECT region, COUNT(*) AS n FROM customers GROUP BY region"
    fastmcp call steps/step_c_query.py run_query sql="DELETE FROM orders"   # rejected
"""

import sqlite3
import time
from pathlib import Path
from typing import Annotated

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError
from pydantic import Field

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "sales.db"
QUERY_TIMEOUT_S = 5

mcp = FastMCP(
    "sales-data",
    instructions=(
        "Read-only access to the Blue Ridge Outfitters sales database (SQLite). "
        "Call list_tables, read schema://{table} for columns, then use run_query. "
        "Revenue = quantity * unit_price * (1 - discount), from order_items."
    ),
)


def connect() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    deadline = time.monotonic() + QUERY_TIMEOUT_S
    # Abort runaway queries (e.g. an accidental cross join).
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    return con


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
        if table not in table_names(con):
            raise ResourceError(f"Unknown table '{table}'. Known: {', '.join(table_names(con))}")
        ddl = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    lines = [f"{c[1]} {c[2]}" for c in cols]
    return f"Table: {table}\nColumns:\n  " + "\n  ".join(lines) + f"\n\nDDL:\n{ddl}"


def check_sql(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        raise ToolError("Send exactly one statement (no ';' separated batches).")
    first = cleaned.split(None, 1)[0].upper() if cleaned else ""
    if first not in {"SELECT", "WITH"}:
        raise ToolError("Only read queries are allowed: start with SELECT or WITH.")
    return cleaned


@mcp.tool(annotations={"readOnlyHint": True})
def run_query(
    sql: Annotated[str, Field(description="A single SQLite SELECT (or WITH ... SELECT) statement.")],
    max_rows: Annotated[int, Field(ge=1, le=200, description="Row cap for the result.")] = 50,
) -> dict:
    """Run a read-only SQL query against the sales database and return the rows.

    Tips: aggregate in SQL (GROUP BY, SUM, AVG) rather than pulling raw rows.
    Dates are ISO text, so use strftime('%Y-%m', order_date) to group by month.
    """
    cleaned = check_sql(sql)
    try:
        with connect() as con:
            cur = con.execute(cleaned)
            columns = [d[0] for d in cur.description or []]
            rows = cur.fetchmany(max_rows + 1)
    except sqlite3.OperationalError as e:
        # Includes syntax errors, unknown columns, attempted writes, and timeouts.
        raise ToolError(f"SQLite error: {e}") from e

    truncated = len(rows) > max_rows
    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:max_rows]],
        "row_count": min(len(rows), max_rows),
        "truncated": truncated,
    }


if __name__ == "__main__":
    mcp.run()
