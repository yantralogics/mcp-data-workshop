# MCP Data Workshop

A 45-minute, hands-on introduction to the **Model Context Protocol (MCP)** for data
analysts and engineers. You'll build a Python MCP server that lets an AI assistant
explore and query a SQLite sales database safely.

> **Start here:** follow [`TUTORIAL.md`](TUTORIAL.md) step by step.

## Before the session (10 minutes, please do this in advance)

### What to install

1. **Python 3.10 or newer.** Check with `python3 --version` (macOS/Linux) or
   `py --version` (Windows). If it's older, install a current version from
   [python.org](https://www.python.org/downloads/).
2. **Node.js 18+**. Only needed for the MCP Inspector (a browser debugging UI).
3. **VS Code** with the **GitHub Copilot Chat** extension, signed in. It's the MCP host
   for the final step. Open the `mcp-data-workshop` folder itself as the workspace.

### Set up the virtual environment

A virtual environment (venv) is a private folder of Python packages for this project,
so the workshop's dependencies don't touch anything else on your machine. We create it
in a folder called `.venv` inside the repo. The VS Code config expects that exact name.

**macOS / Linux**

```bash
cd mcp-data-workshop
python3 -m venv .venv                  # 1. create it (one time)
source .venv/bin/activate              # 2. activate it (every new terminal)
python -m pip install --upgrade pip    # 3. update the installer
pip install -r requirements-dev.txt    # 4. install pinned dependencies + test tools
```

**Windows (PowerShell)**

```powershell
cd mcp-data-workshop
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

If PowerShell refuses to run `Activate.ps1` ("running scripts is disabled"), run this
once, then activate again:
`Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned`.
In the older Command Prompt (`cmd`), activate with `.venv\Scripts\activate.bat` instead.

**How to tell it's active:** your prompt starts with `(.venv)`, and `python --version`
shows 3.10 or newer. Run `deactivate` to leave it. Open a new terminal? Activate again.
In VS Code, run **Python: Select Interpreter** and pick the `.venv` one, and new
terminals will activate it automatically.

### Check everything works

With the venv active:

```bash
python -m pytest -q          # expect: 12 passed
python client_demo.py        # expect: tools, a revenue table, a blocked DROP
```

If both succeed, you're ready.

<details>
<summary>Prefer <a href="https://docs.astral.sh/uv/">uv</a>? (optional)</summary>

`uv sync` creates the same `.venv` from `uv.lock`. Then either activate it as above or
prefix commands with `uv run` (e.g. `uv run pytest -q`). The VS Code config works with
both, because both create `.venv`.
</details>

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
| `.vscode/mcp.json` | Ready-made VS Code config that connects the finished server |
| `requirements.txt` | Pinned runtime dependencies for `pip` |
| `requirements-dev.txt` | Runtime dependencies plus pytest |
| `pyproject.toml`, `uv.lock` | Same dependencies, for `uv` users |

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

Works on **Python 3.10 and newer** (tested on 3.10 and 3.13). Built with
**FastMCP 4.1.1** against the **MCP 2026-07-28** specification. Exact versions of every
package are pinned in `requirements.txt` (for pip) and `uv.lock` (for uv).
MCP evolves quickly. If you read older tutorials online, expect differences.
In particular, the 2026-07-28 revision made the protocol stateless.
