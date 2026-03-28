"""
AI-Powered Business Automation Assistant
Uses Claude API with tool-chaining to answer business questions.
Session history is saved to SQLite so conversations persist.
"""

import json
import sqlite3
import anthropic

# ----------------------------------------------------------------
# Mock business data (simulates what would come from a real database)
# ----------------------------------------------------------------

SALES_DATA = [
    {"product": "Enterprise Plan", "amount": 31000, "month": "2026-03"},
    {"product": "Premium Plan",    "amount": 12400, "month": "2026-03"},
    {"product": "Basic Plan",      "amount":  5200, "month": "2026-03"},
    {"product": "Add-ons",         "amount":  2800, "month": "2026-03"},
]

EXPENSE_DATA = [
    {"category": "Salaries",          "amount": 42000, "month": "2026-03"},
    {"category": "Marketing",         "amount":  5800, "month": "2026-03"},
    {"category": "Cloud hosting",     "amount":  3200, "month": "2026-03"},
    {"category": "Software licenses", "amount":  1200, "month": "2026-03"},
]

INVENTORY_DATA = [
    {"item": "API tokens",    "qty": 12,  "reorder_at": 5},
    {"item": "Storage (TB)",  "qty": 2,   "reorder_at": 3},
    {"item": "Support seats", "qty": 8,   "reorder_at": 10},
    {"item": "Trial accounts","qty": 45,  "reorder_at": 20},
]

# ----------------------------------------------------------------
# Tool functions
# ----------------------------------------------------------------

def lookup_sales(month=None):
    """Return sales records, optionally filtered by month."""
    records = SALES_DATA if not month else [r for r in SALES_DATA if r["month"] == month]
    total = sum(r["amount"] for r in records)
    return {"records": records, "total": total}


def query_expenses(month=None):
    """Return expense records, optionally filtered by month."""
    records = EXPENSE_DATA if not month else [r for r in EXPENSE_DATA if r["month"] == month]
    total = sum(r["amount"] for r in records)
    return {"records": records, "total": total}


def check_inventory(low_stock_only=False):
    """Return inventory. If low_stock_only=True, only return items below reorder threshold."""
    if low_stock_only:
        records = [r for r in INVENTORY_DATA if r["qty"] <= r["reorder_at"]]
    else:
        records = INVENTORY_DATA
    return {"records": records, "low_stock_count": sum(1 for r in INVENTORY_DATA if r["qty"] <= r["reorder_at"])}


def generate_report(month):
    """Combine sales, expenses, and inventory into a summary report."""
    sales    = lookup_sales(month)
    expenses = query_expenses(month)
    inventory = check_inventory(low_stock_only=True)
    net = sales["total"] - expenses["total"]
    return {
        "month": month,
        "total_revenue": sales["total"],
        "total_expenses": expenses["total"],
        "net": net,
        "profitable": net > 0,
        "low_stock_items": [r["item"] for r in inventory["records"]],
    }


TOOL_FUNCTIONS = {
    "lookup_sales":    lookup_sales,
    "query_expenses":  query_expenses,
    "check_inventory": check_inventory,
    "generate_report": generate_report,
}

# Tool schemas for Claude
TOOLS = [
    {
        "name": "lookup_sales",
        "description": "Look up sales revenue data. Can filter by month (YYYY-MM format).",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Month to filter by, e.g. '2026-03'. Optional."}
            },
        },
    },
    {
        "name": "query_expenses",
        "description": "Look up expense data by category. Can filter by month.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Month to filter by. Optional."}
            },
        },
    },
    {
        "name": "check_inventory",
        "description": "Check inventory levels. Set low_stock_only=true to see only items below reorder threshold.",
        "input_schema": {
            "type": "object",
            "properties": {
                "low_stock_only": {"type": "boolean", "description": "Only return low stock items."}
            },
        },
    },
    {
        "name": "generate_report",
        "description": "Generate a full business summary report for a given month.",
        "input_schema": {
            "type": "object",
            "properties": {
                "month": {"type": "string", "description": "Month in YYYY-MM format, e.g. '2026-03'"}
            },
            "required": ["month"],
        },
    },
]

SYSTEM_PROMPT = """You are a business automation assistant for a small SaaS company.
You have tools to look up sales, expenses, inventory, and generate reports.
When the user asks a question, use the right tool(s) to get the data, then give a clear answer with exact numbers.
If a question needs multiple tools, call them one after another before answering."""

# ----------------------------------------------------------------
# SQLite — save session history so conversations persist
# ----------------------------------------------------------------

def init_db(db_path="sessions.db"):
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            role       TEXT NOT NULL,
            content    TEXT NOT NULL
        )
    """)
    conn.commit()
    return conn


def save_message(conn, session_id, role, content):
    conn.execute(
        "INSERT INTO messages (session_id, role, content) VALUES (?, ?, ?)",
        (session_id, role, content)
    )
    conn.commit()


def load_history(conn, session_id):
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE session_id = ? ORDER BY id",
        (session_id,)
    ).fetchall()
    return [{"role": row[0], "content": row[1]} for row in rows]


# ----------------------------------------------------------------
# Agentic loop — tool-chaining
# ----------------------------------------------------------------

def run_agent(client, messages):
    """
    Send messages to Claude. If Claude wants to call a tool, run it
    and send the result back. Repeat until Claude gives a final answer.
    """
    current_messages = list(messages)

    for _ in range(5):  # max 5 rounds of tool calls
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=current_messages,
        )

        # Claude is done — return the text answer
        if response.stop_reason == "end_turn":
            return " ".join(b.text for b in response.content if hasattr(b, "text"))

        # Claude wants to call tool(s)
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    print(f"  [calling tool: {block.name}]")
                    try:
                        result = TOOL_FUNCTIONS[block.name](**block.input)
                    except Exception as e:
                        result = {"error": str(e)}
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result),
                    })

            current_messages.append({"role": "assistant", "content": response.content})
            current_messages.append({"role": "user",      "content": tool_results})

    return "Sorry, I couldn't complete that request."


# ----------------------------------------------------------------
# Main — CLI chat loop
# ----------------------------------------------------------------

def main():
    import time

    client = anthropic.Anthropic()
    db = init_db()

    session_id = f"session_{int(time.time())}"
    print("=== Business Automation Assistant ===")
    print("Type 'quit' to exit.\n")

    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() == "quit":
            print("Bye!")
            break

        save_message(db, session_id, "user", user_input)

        history = load_history(db, session_id)
        reply = run_agent(client, history)

        save_message(db, session_id, "assistant", reply)
        print(f"\nAssistant: {reply}\n")

    db.close()


if __name__ == "__main__":
    main()
