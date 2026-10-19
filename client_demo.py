"""The other side of the wire: an MCP CLIENT, with no LLM involved.

This is exactly what a host app (Claude, VS Code, Cursor...) does before and
during a conversation: discover capabilities, then call them on the model's
behalf. Seeing it in plain Python removes most of the magic.

    python client_demo.py                     # spawns steps/step_d_prompt.py over stdio
    python client_demo.py server.py           # ...or point it at your own server
    python client_demo.py http://127.0.0.1:8000/mcp   # ...or a running HTTP server
"""

import asyncio
import json
import sys
from pathlib import Path

from fastmcp import Client

ARG = sys.argv[1] if len(sys.argv) > 1 else "steps/step_d_prompt.py"
# A URL -> Streamable HTTP; a Path to a .py file -> launched as a stdio subprocess.
TARGET = ARG if ARG.startswith("http") else Path(ARG)


def show(title: str, obj) -> None:
    print(f"\n=== {title} ===")
    print(obj if isinstance(obj, str) else json.dumps(obj, indent=2, default=str))


async def main() -> None:
    # Same client API regardless of transport.
    async with Client(TARGET) as client:
        # 1. Discovery: this list (names, descriptions, schemas) is what the model sees.
        tools = await client.list_tools()
        show("tools", [{"name": t.name, "description": t.description} for t in tools])

        templates = await client.list_resource_templates()
        resources = await client.list_resources()
        show("resources", [r.uri_template for r in templates] + [str(r.uri) for r in resources])

        prompts = await client.list_prompts()
        show("prompts", [p.name for p in prompts])

        if not any(t.name == "run_query" for t in tools):
            print("\n(This server has no run_query tool yet; stopping after discovery.)")
            return

        # 2. Reading a resource: the APPLICATION chooses to pull this into context.
        schema = await client.read_resource("schema://orders")
        show("resource schema://orders", schema[0].text)

        # 3. Calling a tool: in a real host, the MODEL chose these arguments.
        result = await client.call_tool(
            "run_query",
            {
                "sql": """
                    SELECT c.region,
                           ROUND(SUM(i.quantity * i.unit_price * (1 - i.discount)), 2) AS revenue
                    FROM order_items i
                    JOIN orders o    ON o.order_id = i.order_id
                    JOIN customers c ON c.customer_id = o.customer_id
                    WHERE o.status NOT IN ('Cancelled', 'Returned')
                    GROUP BY c.region ORDER BY revenue DESC
                """,
                "max_rows": 10,
            },
        )
        data = result.data
        table = "\n".join(f"  {r[0]:<10} {r[1]:>12,.2f}" for r in data["rows"])
        show("tool run_query -> structured result", f"  columns={data['columns']}  "
             f"row_count={data['row_count']}  truncated={data['truncated']}\n{table}")

        # 4. A guardrail in action: errors come back as results the model can read.
        bad = await client.call_tool("run_query", {"sql": "DROP TABLE orders"}, raise_on_error=False)
        show("tool run_query (blocked)", {"is_error": bad.is_error, "message": bad.content[0].text})

        # 5. Getting a prompt: the USER picked it; it becomes the opening message.
        if any(p.name == "analyze_table" for p in prompts):
            prompt = await client.get_prompt("analyze_table", {"table": "orders", "focus": "trends"})
            show("prompt analyze_table", prompt.messages[0].content.text)


if __name__ == "__main__":
    asyncio.run(main())
