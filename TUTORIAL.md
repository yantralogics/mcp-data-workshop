# Build Your First MCP Server: A Hands-On Tutorial for Data Teams

**Time:** 45 minutes · **Stack:** Python, FastMCP, SQLite · **Level:** you know how LLMs
and tool calling work, and you've built a web app or dashboard.

By the end you will have a working MCP server that lets an AI assistant discover,
inspect and query a sales database, with guardrails that you wrote yourself.
You'll also understand what's happening on the wire and how to take it further.

| Part | Minutes | What you do |
|---|---|---|
| 0. Setup check | before | Create the venv, install, run the tests |
| 1. Concepts | 0–20 | Why MCP, the mental model, design principles (slides) |
| 2. Build | 20–40 | Checkpoints A → D in `server.py` |
| 3. Connect VS Code | 38–42 | Ask questions in plain English |
| 4. Wrap-up | 40–45 | Recap and stretch challenges |

> **Fell behind?** Every checkpoint has a complete, working file in `steps/`. Copy it
> over `server.py` (e.g. `cp steps/step_b_tables.py server.py`, then fix `DB_PATH`, see
> the note in Checkpoint B), or just run the step file directly. Nobody should be stuck.

---

## Part 0: Setup check (do this before the session)

You need **Python 3.10 or newer**. Create a virtual environment called `.venv` in the
repo folder and install the pinned dependencies into it. (The README has the same steps
with more explanation, including PowerShell troubleshooting.)

**macOS / Linux**

```bash
cd mcp-data-workshop
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

**Windows (PowerShell)**

```powershell
cd mcp-data-workshop
py -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
```

Then check:

```bash
python -m pytest -q          # 12 passed
python client_demo.py        # prints tools, a revenue table, a blocked DROP TABLE
```

> **Every command in this tutorial assumes two things:** you're in the repo folder, and the
> venv is **active**: your prompt starts with `(.venv)`. Each new terminal needs
> activating again (`source .venv/bin/activate`, or `.venv\Scripts\Activate.ps1` on
> Windows). Seeing `command not found: fastmcp` or `No module named fastmcp`? The venv
> isn't active.
>
> Using [uv](https://docs.astral.sh/uv/) instead? `uv sync` creates the same `.venv`;
> activate it, or prefix commands with `uv run`.

---

## Part 1: Concepts in five minutes of reading

These are covered on the slides. Here's the short version to refer back to.

### Why MCP exists

Before MCP, every AI app needed custom glue for every data source:
*N apps × M sources* integrations. MCP is a shared protocol, so you write a server
once and any compliant host can use it: *N + M*. If you've used ODBC/JDBC, it's the
same idea for LLM apps.

### Three roles

```
┌───────────────────────── HOST (Claude, VS Code, Cursor...) ─────────────────────────┐
│                                                                                     │
│   LLM  ◄──── decides which tool to call ────►  MCP CLIENT  ◄── JSON-RPC ──►  MCP SERVER  ──► your DB / API / files
│                                                (1 per server)                (your code)
└─────────────────────────────────────────────────────────────────────────────────────┘
```

- **Host**: the app the user talks to. It owns the LLM and the UI.
- **Client**: a connector inside the host, one per server.
- **Server**: your program. It exposes capabilities and runs them.

**The model never talks to your server directly.** The host shows the model your
tool list, the model asks to call one, and the host makes the call and feeds the result
back into the context. The host is also where user approval happens.

### Three primitives, defined by who's in control

| Primitive | Who decides to use it | Analogy | In our server |
|---|---|---|---|
| **Tool** | The **model** | A function / POST endpoint | `list_tables`, `run_query` |
| **Resource** | The **application** or user | A file / GET endpoint | `schema://{table}`, `docs://glossary` |
| **Prompt** | The **user** | A saved template / slash command | `analyze_table`, `kpi_summary` |

### Two transports

- **stdio**: the host launches your server as a subprocess and talks over
  stdin/stdout. Local, zero network setup, one user. **Start here.**
- **Streamable HTTP**: your server runs as a web service at a URL. Shareable,
  remote, many clients. Same code; only the `run()` call changes.

### Design principles (the part that actually matters)

1. **Descriptions are prompts.** The model picks tools by reading names and docstrings.
   Write them for the model: when to use it, what it returns, an example.
2. **Type hints are the contract.** They become JSON Schema, which the host validates
   *before* your code runs.
3. **Return small, structured results.** Aggregate in SQL. Cap rows. Don't paste
   10,000 rows into the context window.
4. **Guardrails live in the server, not the prompt.** Read-only connections, allow-lists,
   timeouts. Assume anything the model sends you could be wrong or adversarial.
5. **Errors are information.** A clear error message lets the model fix its own mistake.

---

## Part 2: Build it

Open `server.py` in your editor. It has the imports, a `DB_PATH`, a `connect()` helper,
and TODO markers. Keep a terminal open in the repo folder.

### Checkpoint A: hello, MCP (≈5 min)

Replace `# TODO A` with:

```python
@mcp.tool
def greet(name: str) -> str:
    """Say hello to someone. Use this to confirm the server is connected."""
    return f"Hello, {name}! The sales-data MCP server is up."
```

That's a complete MCP server. Now look at it the way a host does:

```bash
fastmcp list server.py --input-schema
```

You'll see the tool's name, its description (your docstring) and its input schema,
generated from `name: str`:

```json
{"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]}
```

Call it without any LLM:

```bash
fastmcp call server.py greet name=Ada
# {"result": "Hello, Ada! The sales-data MCP server is up."}
```

**Now open the MCP Inspector**, a browser UI that shows the raw protocol:

```bash
fastmcp dev inspector server.py
```

In the browser: **Connect** → **Tools** → **List Tools** → `greet` → enter a name →
**Run Tool**. Open the history panel and look at the JSON-RPC request and response.
That's all MCP is: structured messages describing and invoking capabilities.

> **What just happened:** `@mcp.tool` registered a function. FastMCP read its signature
> and docstring to build the tool definition, and `mcp.run()` started a stdio server.
> You'll use `fastmcp list` / `fastmcp call` / the Inspector throughout. They let you
> debug a server without burning LLM tokens or guessing what the model saw.

**Gotcha:** in a stdio server, stdout *is* the protocol channel. A stray `print()`
corrupts the stream. Log to stderr instead (`print(..., file=sys.stderr)` or `logging`).

### Checkpoint B: tools vs. resources (≈5 min)

Now connect to real data. `connect()` is already provided and opens the database
**read-only** (`mode=ro`). Replace `# TODO B1` and `# TODO B2` with:

```python
from fastmcp.exceptions import ResourceError   # put this with the other imports


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
        if table not in table_names(con):  # allow-list: never interpolate unchecked input
            raise ResourceError(f"Unknown table '{table}'. Known: {', '.join(table_names(con))}")
        ddl = con.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()[0]
        cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    lines = [f"{c[1]} {c[2]}" for c in cols]
    return f"Table: {table}\nColumns:\n  " + "\n  ".join(lines) + f"\n\nDDL:\n{ddl}"
```

Try both:

```bash
fastmcp list server.py --resources
fastmcp call server.py list_tables
fastmcp call server.py schema://orders
fastmcp call server.py schema://nope      # helpful error listing real tables
```

`list_tables` should report customers 300, products 26, orders 2,500, order_items 4,348.

Notice that `fastmcp list --resources` says **Resources (0)**. That's expected:
`schema://{table}` is a resource *template*, and MCP discovers templates through a
separate call (`resources/templates/list`). The Inspector's Resources tab and
`client_demo.py` both show templates and concrete resources side by side.

> **What just happened:** `list_tables` is a **tool**: the model decides to call it.
> `schema://{table}` is a **resource template**: one function serving many URIs,
> loaded as context by the app or the user (in most hosts, by attaching it to the chat).
> `readOnlyHint` tells the host this tool has no side effects, which hosts can use
> when deciding whether to ask the user for approval.

**Gotcha:** `DB_PATH` is built from `__file__`, not the current directory. Hosts launch
your server from wherever they like, and relative paths break immediately. (If you
copied a file from `steps/` into the repo root, change `.parent.parent` to `.parent`.)

### Checkpoint C: let the model query, safely (≈6 min)

This is the tool that does the real work. Replace `# TODO C` with:

```python
from typing import Annotated                 # put these with the other imports
from fastmcp.exceptions import ToolError
from pydantic import Field


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
        raise ToolError(f"SQLite error: {e}") from e

    return {
        "columns": columns,
        "rows": [list(r) for r in rows[:max_rows]],
        "row_count": min(len(rows), max_rows),
        "truncated": len(rows) > max_rows,
    }
```

Try the happy path and then attack it:

```bash
fastmcp call server.py run_query \
  sql="SELECT region, COUNT(*) AS customers FROM customers GROUP BY region"

fastmcp call server.py run_query sql="DELETE FROM orders"          # blocked by check_sql
fastmcp call server.py run_query sql="SELECT 1; DROP TABLE orders" # blocked by check_sql
fastmcp call server.py run_query sql="SELECT nope FROM orders"     # "no such column"
fastmcp call server.py run_query sql="SELECT * FROM orders" max_rows=5000  # schema rejects
```

> **What just happened: three layers of defence.**
> 1. **Schema validation**: `max_rows` must be 1–200, enforced before your code runs.
> 2. **`check_sql`**: friendly, specific errors the model can learn from.
> 3. **Read-only connection**: the real guarantee. Even a query that slips past the
>    keyword check (try `WITH x AS (SELECT 1) INSERT INTO products ...`) cannot write.
>
> The string check is for good error messages. The read-only connection is for safety.
> Never rely on the string check alone.
>
> `ToolError` messages go back to the model as an error result. In practice the model
> reads "no such column: nope", checks the schema, and retries with the right column.

The finished `steps/step_c_query.py` also adds a 5-second query timeout using SQLite's
progress handler, so an accidental cross join can't hang the server. Worth copying.

### Checkpoint D: prompts and HTTP (≈4 min)

Prompts package up *how your team analyses things*. Replace `# TODO D` with:

```python
from typing import Literal                   # put this with the other imports


@mcp.prompt
def analyze_table(
    table: str,
    focus: Literal["data quality", "trends", "segments"] = "trends",
) -> str:
    """Start a structured exploratory analysis of one table."""
    return f"""You are a careful data analyst working with the sales database.

Analyse the `{table}` table with a focus on **{focus}**.

1. Read the resource schema://{table}.
2. Use run_query to profile the table (row counts, nulls, distinct values, ranges).
3. Run 2-4 targeted aggregate queries for the {focus} focus. Keep max_rows small.
4. Report: key findings as bullets, the SQL you ran, and one follow-up question.

Never invent numbers: every figure must come from a query result."""
```

```bash
fastmcp list server.py --resources --prompts
fastmcp call server.py analyze_table --prompt table=orders focus=trends
```

**Same server, different transport.** Run the finished version over HTTP:

```bash
python steps/step_d_prompt.py --http         # serves http://127.0.0.1:8000/mcp
```

In a second terminal, use the same client code against the URL:

```bash
python client_demo.py http://127.0.0.1:8000/mcp
```

Nothing about your tools changed. Transport is a deployment decision, not a design one.
(Stop the server with Ctrl+C.)

> **What just happened:** a prompt shows up in hosts as a slash command or menu item.
> The user picks it, fills in `table` and `focus`, and the rendered text becomes the
> opening message. The model then uses your tools and resources to carry it out.
> The final version in `steps/step_d_prompt.py` also adds a `docs://glossary` resource
> (agreed metric definitions) and a `kpi_summary` prompt.

### Bonus: the client side, with no LLM

```bash
python client_demo.py              # or: python client_demo.py server.py
```

Read `client_demo.py`. It's ~80 lines and does exactly what a host does: list tools,
resources and prompts (this is what the model gets to see), read a resource, call a tool,
handle an error, render a prompt. Hosts add an LLM in the middle that chooses
*which* calls to make. That's the whole trick.

---

## Part 3: Connect VS Code (≈4 min)

Now plug the finished server into a real host. Here the host is **VS Code**:
GitHub Copilot Chat (in Agent mode) is the LLM, VS Code runs the MCP client, and your
server doesn't change at all.

**You need:**

- VS Code with the GitHub Copilot Chat extension, signed in.
- The repo opened **as the workspace folder**: *File → Open Folder…* and pick
  `mcp-data-workshop` itself, not its parent. The config below relies on that.

We use the finished server (`steps/step_d_prompt.py`) so everyone has identical tools.

### 3.1 Get comfortable with the integrated terminal

Everything in this part can be checked from VS Code's built-in terminal, which is the
fastest way to find out what's wrong when something doesn't connect.

- **Open it:** *View → Terminal*, or press <kbd>Ctrl</kbd>+<kbd>`</kbd> (backtick; same
  keys on macOS). It opens in the workspace folder.
- **Check where you are and that the files are there:**

  ```bash
  pwd          # macOS/Linux: should end in /mcp-data-workshop
               # Windows PowerShell: use  Get-Location
  ls           # should list server.py, steps/, data/, .vscode/ ...
  ```

- **Activate the virtual environment** if your prompt doesn't already start with `(.venv)`:

  ```bash
  source .venv/bin/activate        # macOS/Linux
  .venv\Scripts\Activate.ps1        # Windows PowerShell
  ```

  Tip: run **Python: Select Interpreter** from the Command Palette and choose the
  `.venv` interpreter. VS Code then activates it automatically in every new terminal.

- **Split the terminal** with the split icon in the terminal toolbar. Keep one pane for
  long-running servers and one for commands. <kbd>Ctrl</kbd>+<kbd>C</kbd> stops a running server.

### 3.2 Test the exact command VS Code will run

VS Code will start your server by running the venv's own Python on the step file:
`.venv/bin/python steps/step_d_prompt.py`. Using that interpreter directly means the
server finds its packages even though VS Code never "activates" anything. Run the
equivalent yourself first. If it fails here, it will fail in VS Code too, and the terminal
shows the real error much more clearly.

```bash
fastmcp list steps/step_d_prompt.py
```

Expected: `Tools (2)` listing `list_tables` and `run_query`.

Now try starting it bare, the way a host does:

```bash
.venv/bin/python steps/step_d_prompt.py           # macOS/Linux
.venv\Scripts\python.exe steps\step_d_prompt.py   # Windows
```

It appears to **hang**. That's correct: a stdio server sits waiting for JSON-RPC
messages on stdin. Press <kbd>Ctrl</kbd>+<kbd>C</kbd>. (This is also why a stray `print()`
breaks stdio servers: stdout *is* the message channel.)

If you get `No such file or directory` instead, the venv doesn't exist yet, or it's
named something other than `.venv`. Go back to Part 0.

### 3.3 Add the server to VS Code

The repo already contains **`.vscode/mcp.json`**. Open it from the terminal:

```bash
code .vscode/mcp.json
```

```json
{
  "servers": {
    "sales-data": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["${workspaceFolder}/steps/step_d_prompt.py"]
    }
  }
}
```

What each part does:

| Field | Meaning |
|---|---|
| `"servers"` | VS Code's top-level key. (Claude-style configs on the web use `"mcpServers"`. Don't mix them up when copying examples.) |
| `"sales-data"` | The server's name. It appears in the tools list and in prompt names. |
| `"type": "stdio"` | VS Code launches the server as a subprocess. |
| `"command"` | The venv's Python. Pointing at it directly is what makes the installed packages available. |
| `"args"` | The server file to run: exactly the command you tested in 3.2. |
| `${workspaceFolder}` | Filled in by VS Code with the repo's path, so no absolute paths are needed. |

**On Windows**, the venv's Python lives in a different place. Change the `"command"` line to:

```json
"command": "${workspaceFolder}\\.venv\\Scripts\\python.exe",
```

If `code` isn't recognised on macOS, open the Command Palette (<kbd>⇧⌘P</kbd>), run
**Shell Command: Install 'code' command in PATH**, then open a new terminal. On Windows,
the installer adds it by default.

**Other ways to add a server** (pick only one, or the tools will appear twice):

- **Command Palette:** run **MCP: Add Server**, choose a stdio command, follow the prompts,
  and pick *Workspace* to write `.vscode/mcp.json`.
- **Terminal, for your user profile (all workspaces):** `code --add-mcp` takes the server
  as JSON. A user-level server has no workspace, so use absolute paths. On macOS/Linux,
  from the repo folder:

  ```bash
  REPO="$(pwd)"
  code --add-mcp "{\"name\":\"sales-data\",\"command\":\"$REPO/.venv/bin/python\",\"args\":[\"$REPO/steps/step_d_prompt.py\"]}"
  ```

  On Windows, stick with the workspace file. Quoting JSON in PowerShell is error-prone.

### 3.4 Start the server and check it's running

1. Open the Command Palette (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>P</kbd> /
   <kbd>⇧⌘P</kbd>) and run **MCP: List Servers**.
2. Select **sales-data** and choose **Start**. The first time, VS Code may ask whether you
   trust the server. It's your code, so accept.
3. Run **MCP: List Servers** → **sales-data** → **Show Output**. This is the server's log
   (its stderr). Look for:

   ```
   Starting MCP server 'sales-data' with transport 'stdio'
   ```

   Keep this panel handy. Python tracebacks, database errors and `ToolError`s all land here.

### 3.5 Use it from Copilot Chat

1. Open the **Chat** view and switch the mode dropdown to **Agent**.
2. Click the **Tools** button (the tool icon in the chat input). You should see
   **sales-data** with `list_tables` and `run_query`. Leave them ticked.
3. Ask a question (see the list below). Before each call, VS Code shows the tool name and
   its arguments, including the exact SQL. You can **edit the arguments** before allowing it.
   The **Continue** dropdown can auto-approve a tool for the session. Approve one at a
   time today so you can watch what the model does.
4. **Use the prompt:** type `/mcp.sales-data.analyze_table` in the chat box, then fill in
   `table` (e.g. `customers`) and `focus` when asked.
5. **Attach a resource:** click **Add Context** → **MCP Resources** →
   `schema://{table}`, and enter `orders`. The schema is now in the conversation as
   context: the *application* loaded it, not the model.

**Ask it things:**

- *"What tables do you have access to, and what's in them?"*
- *"Which region brought in the most net revenue?"* → Northeast, about $302k
- *"Which product category is the biggest earner?"* → Camping, about $285k
- *"What was our best month?"* → December 2025, about $100k
- *"Compare Q2 2026 to Q1 2026."* → net revenue up ~70% ($190k vs $111k)
- *"Try to delete the orders table."* → watch your guardrails respond

If the model reports a number, ask it *"show me the SQL"*. Every figure should be traceable
to a query. That habit matters more than any single feature.

### 3.6 Edit, restart, repeat

VS Code caches the tool list. After you change server code, restart the server:
**MCP: List Servers** → **sales-data** → **Restart**.

To try **your own** `server.py` instead of the finished one, change the last argument in
`.vscode/mcp.json` to `"${workspaceFolder}/server.py"`, save, and restart.

### Optional: connect over HTTP and watch the traffic

In one terminal pane, start the server as a web service and leave it running:

```bash
python steps/step_d_prompt.py --http
```

Add a second entry inside `"servers"` in `.vscode/mcp.json`, then start it from
**MCP: List Servers**:

```json
"sales-data-http": {
  "type": "http",
  "url": "http://127.0.0.1:8000/mcp"
}
```

Stop or untick the stdio `sales-data` server first so the tools aren't listed twice.
Ask Copilot a question and watch the terminal: every tool call shows up as a
`POST /mcp` line. Same tools, different transport.

**Not showing up?** See Troubleshooting below. The usual causes are opening the wrong
folder, a missing or inactive venv, or the server needing a restart.

---

## Part 4: Wrap-up and stretch challenges

### The recap in one slide

- MCP standardises how AI apps reach tools and data: write the connector once.
- **Host ↔ client ↔ server**. The model never touches your server; the host mediates.
- **Tools** (model chooses), **resources** (app chooses), **prompts** (user chooses).
- **stdio** for local, **Streamable HTTP** for shared. Same code.
- Descriptions are prompts. Types are contracts. Guardrails live in the server.

### Take-home challenges (pick one)

1. **Chart tool.** Add `plot_query(sql, kind="bar")` that runs a query with matplotlib
   and returns an image (`from fastmcp.utilities.types import Image`).
2. **Semantic layer.** Replace free-form SQL with `get_metric(metric, group_by, start, end)`
   built from the glossary. Fewer ways to be wrong, and arguably safer than raw SQL.
3. **Wrap an API.** Point a server at an internal REST API or your dashboard's backend.
   Start with read-only `GET` endpoints.
4. **Share it.** Run with `--http`, put it on a team machine, and connect two hosts to it.
   Then read the MCP authorization docs before doing this for real.
5. **Test like you mean it.** Add tests in `tests/` for every guardrail you add.
   `Client(mcp)` connects in-memory, so tests run in milliseconds.

### Where to go next

- MCP specification and docs: <https://modelcontextprotocol.io>
- FastMCP docs: <https://gofastmcp.com>
- MCP Inspector: <https://github.com/modelcontextprotocol/inspector>

---

## Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| VS Code shows no tools, or the server errors | Run **MCP: List Servers** → **sales-data** → **Show Output** to see the real error. Check that you opened the `mcp-data-workshop` folder itself, since `${workspaceFolder}` depends on it. |
| `unable to open database file` | `DB_PATH` is wrong for where the file lives. Check `.parent` vs `.parent.parent`. |
| Server connects then errors mysteriously | A `print()` to stdout is corrupting the stdio stream. Log to stderr. |
| `spawn ... .venv/bin/python ENOENT` | The venv is missing or named differently. Create it as `.venv` in the repo (Part 0). On Windows, use the `.venv\Scripts\python.exe` path from 3.3. |
| `No module named fastmcp` / `fastmcp: command not found` | The venv isn't active in this terminal. Activate it (Part 0), or run **Python: Select Interpreter** → `.venv`. |
| `pip` says the package requires a different Python | Your Python is older than 3.10. Install a newer one and recreate the venv. |
| PowerShell: "running scripts is disabled" | Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` once, then activate again. |
| Inspector won't start | Needs Node.js 18+ (`node --version`). |
| Tool changes not visible | VS Code caches the tool list. **MCP: List Servers** → **sales-data** → **Restart**. |
| No Agent mode or Tools button in Chat | The GitHub Copilot Chat extension isn't installed or you're not signed in. |
| Tools appear twice | The server is configured twice (workspace and user, or stdio and HTTP). Remove or stop one. |
| Model ignores your tool | Improve the name and docstring: say *when* to use it. |
| `Address already in use` on `--http` | Another server is on port 8000. Stop it, or change the port. |
| Want a fresh database | `python data/build_db.py` (deterministic, same data every time). |
