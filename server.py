"""YOUR server. Build this up during the workshop, following TUTORIAL.md.

Each TODO matches a checkpoint. If you fall behind, the finished version of
every checkpoint is in steps/ (step_a_hello.py ... step_d_prompt.py).

Run any time with:
    fastmcp list server.py --resources --prompts
    fastmcp dev inspector server.py
"""

import sqlite3
from pathlib import Path

from fastmcp import FastMCP

DB_PATH = Path(__file__).resolve().parent / "data" / "sales.db"

mcp = FastMCP("sales-data")


# --- Checkpoint A ------------------------------------------------------------
# TODO A: add a `greet(name: str) -> str` tool with a helpful docstring.


# --- Checkpoint B ------------------------------------------------------------
def connect() -> sqlite3.Connection:
    """Read-only connection to the workshop database (provided for you)."""
    return sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)


# TODO B1: add a `list_tables()` tool that returns [{"table": ..., "rows": ...}].
# TODO B2: add a `schema://{table}` resource that returns the table's columns.


# --- Checkpoint C ------------------------------------------------------------
# TODO C: add a `run_query(sql, max_rows=50)` tool:
#         SELECT/WITH only, single statement, capped rows, ToolError on problems.


# --- Checkpoint D ------------------------------------------------------------
# TODO D: add an `analyze_table(table, focus)` prompt.


if __name__ == "__main__":
    mcp.run()
