# AI-Powered Business Assistant

A CLI assistant that uses the Claude API with tool-chaining to answer business questions about sales, expenses, and inventory. Conversation history is saved to SQLite so sessions persist between runs.

## How it works

You ask a question through the command line. The assistant runs an agentic loop — it calls whichever tool(s) are needed (up to 5 rounds), collects the results, and returns a numbers-backed answer. Claude decides which tools to call and in what order.

## Project structure

```
├── assistant.py        # All logic: tools, mock data, agentic loop, SQLite, CLI
├── test_assistant.py   # 17-test Pytest suite
├── requirements.txt
└── README.md
```

## Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

Set your Anthropic API key:

```bash
export ANTHROPIC_API_KEY=your_key_here
```

Run the assistant:

```bash
python assistant.py
```

Run tests:

```bash
pytest test_assistant.py -v
```

## Tools

| Tool | What it does |
|---|---|
| `lookup_sales` | Returns sales data, filterable by month (YYYY-MM) |
| `query_expenses` | Returns expense data by category, filterable by month |
| `check_inventory` | Returns inventory levels; supports low-stock-only filter |
| `generate_report` | Combines sales, expenses, and low-stock inventory into a summary |

## Mock data

The assistant uses hardcoded mock data defined directly in `assistant.py` — three Python lists (`SALES_DATA`, `EXPENSE_DATA`, `INVENTORY_DATA`) covering March 2026 figures. There is no external database or file.

## Session persistence

Each run starts a new session (keyed by timestamp). All messages are saved to a local `sessions.db` SQLite file so conversation history is preserved across turns within a session.

## Test coverage

The 17-test suite in `test_assistant.py` covers:

- Tool function correctness (sales totals, expense filtering, inventory thresholds, report generation)
- SQLite session logic (init, save, load, session isolation, empty sessions)
- Agentic loop behaviour (plain responses, tool-chaining, max-round cutoff)

All API calls are mocked using `unittest.mock` — no live API calls required to run the tests.

## Tech

Python · Anthropic Claude API (`claude-haiku-4-5-20251001`) · SQLite · Pytest
