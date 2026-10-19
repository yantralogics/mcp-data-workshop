"""Checkpoint D (final): prompts, and running over HTTP.

New concepts:
  * A PROMPT is a reusable, parameterised template the USER picks
    (it shows up as a slash command or menu item in most hosts).
    It encodes "how we analyse things here" once, for the whole team.
  * Same server, two transports:
      python steps/step_d_prompt.py           -> stdio (local, launched by the host)
      python steps/step_d_prompt.py --http    -> Streamable HTTP on :8000/mcp
                                                 (shareable, remote, many clients)
    Your tools don't change at all. Transport is a deployment decision.

Try it:
    fastmcp list steps/step_d_prompt.py --resources --prompts
    fastmcp call steps/step_d_prompt.py analyze_table --prompt table=orders
"""

import sqlite3
import sys
import time
from pathlib import Path
from typing import Annotated, Literal

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


# ---------------------------------------------------------------- helpers
def connect() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
    deadline = time.monotonic() + QUERY_TIMEOUT_S
    con.set_progress_handler(lambda: 1 if time.monotonic() > deadline else 0, 10_000)
    return con


def table_names(con: sqlite3.Connection) -> list[str]:
    rows = con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r[0] for r in rows]


def check_sql(sql: str) -> str:
    cleaned = sql.strip().rstrip(";").strip()
    if ";" in cleaned:
        raise ToolError("Send exactly one statement (no ';' separated batches).")
    first = cleaned.split(None, 1)[0].upper() if cleaned else ""
    if first not in {"SELECT", "WITH"}:
        raise ToolError("Only read queries are allowed: start with SELECT or WITH.")
    return cleaned


# ---------------------------------------------------------------- tools
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
        raise ToolError(f"SQLite error: {e}") from e

    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:max_rows]],
        "row_count": min(len(rows), max_rows),
        "truncated": len(rows) > max_rows,
    }


# ---------------------------------------------------------------- resources
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


@mcp.resource("docs://glossary", mime_type="text/markdown")
def glossary() -> str:
    """Business definitions the team has agreed on. Load this before reporting numbers."""
    return """# Sales glossary
- **Revenue**: SUM(quantity * unit_price * (1 - discount)) over order_items.
- **Net revenue**: revenue from orders whose status is NOT 'Cancelled' or 'Returned'.
- **AOV** (average order value): net revenue / number of net orders.
- **Active customer**: placed at least one net order in the period.
- Fiscal year = calendar year. Data covers 2025-01-01 to 2026-06-30.
"""


# ---------------------------------------------------------------- prompts
@mcp.prompt
def analyze_table(
    table: str,
    focus: Literal["data quality", "trends", "segments"] = "trends",
) -> str:
    """Start a structured exploratory analysis of one table."""
    return f"""You are a careful data analyst working with the sales database.

Analyse the `{table}` table with a focus on **{focus}**.

1. Read the resource schema://{table} and the glossary at docs://glossary.
2. Use run_query to profile the table (row counts, nulls, distinct values, ranges).
3. Run 2-4 targeted aggregate queries for the {focus} focus. Keep max_rows small.
4. Report: key findings as bullets, the SQL you ran, and one follow-up question.

Never invent numbers: every figure must come from a query result."""


@mcp.prompt
def kpi_summary(period: str = "2026-Q2") -> str:
    """Draft a short KPI summary for a period, using the glossary's definitions."""
    return f"""Produce a KPI summary for {period} from the sales database.

Use docs://glossary for definitions. Report net revenue, net orders, AOV and
active customers, each compared with the previous period, plus the top 3
product categories by net revenue. Show the SQL behind each number."""


if __name__ == "__main__":
    if "--http" in sys.argv:
        # Streamable HTTP: one long-running server, many clients, at http://127.0.0.1:8000/mcp
        mcp.run(transport="http", host="127.0.0.1", port=8000)
    else:
        mcp.run()
