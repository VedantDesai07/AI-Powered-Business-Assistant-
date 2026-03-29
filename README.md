# AI-Powered Business Automation Assistant

A CLI assistant that uses the Claude API with tool-chaining to answer business questions about sales, expenses, and inventory. Conversation history is saved to SQLite so sessions persist between runs.

## How it works

When you ask a question, the assistant figures out which tool(s) to call (e.g. `lookup_sales` → `query_expenses`), calls them in sequence, and uses the returned data to give you a numbers-backed answer. This is called tool-chaining — Claude decides the order automatically.

## Project structure

```
ai_assistant/
├── assistant.py        # Everything: tools, agent loop, SQLite, CLI
├── tests/
│   └── test_assistant.py   # 21 unit tests
├── requirements.txt
└── .gitignore
```

## Setup

```bash
git clone https://github.com/vedantdesai07/ai-business-assistant
cd ai_assistant

pip install -r requirements.txt

# Add your API key
export ANTHROPIC_API_KEY=your_key_here

python assistant.py
```

## Run tests

```bash
pytest tests/ -v
```

## Example questions to try

- "What were total sales in March 2026?"
- "Which inventory items are running low?"
- "Are we profitable this month?"
- "Generate a full report for March 2026"
- "Compare our revenue and expenses"

## Tools

| Tool | What it does |
|------|-------------|
| `lookup_sales` | Returns sales by product, filterable by month |
| `query_expenses` | Returns expenses by category |
| `check_inventory` | Returns inventory levels, can filter to low-stock only |
| `generate_report` | Combines all three into a summary |

## Tech

Python · Claude API · SQLite · Pytest 
