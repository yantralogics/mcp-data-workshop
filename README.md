# MCP Data Workshop

A 45-minute, hands-on introduction to the **Model Context Protocol (MCP)** for data
analysts and engineers. You'll build a Python MCP server that lets an AI assistant
explore and query a SQLite sales database safely.

> **Start here:** follow [`TUTORIAL.md`](TUTORIAL.md) step by step.

## Before the session (10 minutes, please do this in advance)

1. **Python 3.11+** and **[uv](https://docs.astral.sh/uv/)**
   (`curl -LsSf https://astral.sh/uv/install.sh | sh`, or `pip install uv`).
2. **Node.js 18+**. Only needed for the MCP Inspector (a browser debugging UI).
3. An **MCP host** for the final step. Any one of: Claude Desktop, Claude Code,
   VS Code (Copilot agent mode), or Cursor.
4. Set up and check:

   ```bash
   cd mcp-data-workshop
   uv sync                 # creates .venv with pinned dependencies
   uv run pytest -q        # expect: 12 passed
   uv run python client_demo.py   # expect: tools, a revenue table, a blocked DROP
   ```

If all three commands succeed, you're ready.

## What's in the box

| Path | What it is |
|---|---|
| `TUTORIAL.md` | The step-by-step walkthrough for the session |
| `server.py` | **Your** file. A skeleton with TODOs you fill in live |
| `steps/step_a_hello.py` | Checkpoint A: smallest useful server (tools, schemas) |
| `steps/step_b_tables.py` | Checkpoint B: tools vs. resources, real database |
| `steps/step_c_query.py` | Checkpoint C: `run_query` with guardrails |
| `steps/step_d_prompt.py` | Checkpoint D: prompts, HTTP transport (final version) |
| `client_demo.py` | An MCP **client** in plain Python: what a host does under the hood |
| `tests/test_server.py` | In-memory tests, including security checks |
| `data/sales.db` | The dataset (prebuilt, ~7k rows) |
| `data/build_db.py` | Regenerates the dataset deterministically |
| `configs/mcp_host_config.example.json` | Config snippet to connect a host |

Fell behind? Every checkpoint in `steps/` is complete and runnable on its own.

## The dataset

*Blue Ridge Outfitters* is a fictional outdoor-gear retailer, Jan 2025 to Jun 2026.

```
customers (300)    customer_id, name, region, segment, signup_date
products  (26)     product_id, name, category, unit_price
orders    (2,500)  order_id, customer_id, order_date, channel, status
order_items (4,348) order_item_id, order_id, product_id, quantity, unit_price, discount
```

Revenue = `quantity * unit_price * (1 - discount)`. Net revenue excludes
`Cancelled` and `Returned` orders. Data has seasonality and uneven regions, so
there are real patterns to find.

## Versions

Built and tested with **FastMCP 4.1.1** (pinned `>=4.1,<5` in `pyproject.toml`,
exact versions in `uv.lock`) against the **MCP 2026-07-28** specification.
MCP evolves quickly. If you read older tutorials online, expect differences.
In particular, the 2026-07-28 revision made the protocol stateless.
