"""
Tests for the business automation assistant.
Run with: pytest tests/ -v
"""

import json
import sqlite3
import tempfile
import pytest
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from assistant import (
    lookup_sales, query_expenses, check_inventory, generate_report,
    init_db, save_message, load_history, run_agent, TOOL_FUNCTIONS,
)


# ----------------------------------------------------------------
# Tool function tests
# ----------------------------------------------------------------

def test_lookup_sales_returns_all():
    result = lookup_sales()
    assert len(result["records"]) == 4
    assert result["total"] == 51400


def test_lookup_sales_filter_by_month():
    result = lookup_sales(month="2026-03")
    assert all(r["month"] == "2026-03" for r in result["records"])


def test_lookup_sales_bad_month_returns_empty():
    result = lookup_sales(month="2099-01")
    assert result["records"] == []
    assert result["total"] == 0


def test_query_expenses_total():
    result = query_expenses()
    assert result["total"] == 52200


def test_query_expenses_filter():
    result = query_expenses(month="2026-03")
    assert len(result["records"]) > 0


def test_check_inventory_all():
    result = check_inventory()
    assert len(result["records"]) == 4


def test_check_inventory_low_stock_only():
    result = check_inventory(low_stock_only=True)
    # Storage (qty=2, reorder=3) and Support seats (qty=8, reorder=10) are low
    items = [r["item"] for r in result["records"]]
    assert "Storage (TB)" in items
    assert "Support seats" in items
    assert "API tokens" not in items


def test_generate_report_net():
    result = generate_report("2026-03")
    assert result["net"] == 51400 - 52200
    assert result["profitable"] is False


def test_generate_report_has_low_stock():
    result = generate_report("2026-03")
    assert isinstance(result["low_stock_items"], list)
    assert "Storage (TB)" in result["low_stock_items"]


def test_tool_functions_dict_has_all_tools():
    for name in ["lookup_sales", "query_expenses", "check_inventory", "generate_report"]:
        assert name in TOOL_FUNCTIONS


# ----------------------------------------------------------------
# SQLite session tests
# ----------------------------------------------------------------

def test_init_db_creates_table():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/test.db"
        conn = init_db(db_path)
        # Table should exist
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages'"
        ).fetchone()
        assert row is not None
        conn.close()


def test_save_and_load_messages():
    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(f"{tmp}/test.db")
        save_message(conn, "s1", "user", "Hello")
        save_message(conn, "s1", "assistant", "Hi!")
        history = load_history(conn, "s1")
        assert len(history) == 2
        assert history[0]["role"] == "user"
        assert history[1]["content"] == "Hi!"
        conn.close()


def test_sessions_are_isolated():
    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(f"{tmp}/test.db")
        save_message(conn, "session_A", "user", "Message A")
        save_message(conn, "session_B", "user", "Message B")
        assert len(load_history(conn, "session_A")) == 1
        assert len(load_history(conn, "session_B")) == 1
        conn.close()


def test_empty_session_returns_empty_list():
    with tempfile.TemporaryDirectory() as tmp:
        conn = init_db(f"{tmp}/test.db")
        assert load_history(conn, "nonexistent") == []
        conn.close()


# ----------------------------------------------------------------
# Agent loop tests (mocked API)
# ----------------------------------------------------------------

def _mock_text_response(text):
    """Make a mock Claude response that just returns text."""
    block = MagicMock()
    block.type = "text"
    block.text = text
    response = MagicMock()
    response.stop_reason = "end_turn"
    response.content = [block]
    client = MagicMock()
    client.messages.create.return_value = response
    return client


def _mock_tool_then_text(tool_name, tool_input, final_text):
    """Mock Claude calling one tool then returning text."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "tool_123"
    tool_block.name = tool_name
    tool_block.input = tool_input

    first = MagicMock()
    first.stop_reason = "tool_use"
    first.content = [tool_block]

    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = final_text
    second = MagicMock()
    second.stop_reason = "end_turn"
    second.content = [text_block]

    client = MagicMock()
    client.messages.create.side_effect = [first, second]
    return client


def test_agent_plain_response():
    client = _mock_text_response("Total sales are $51,400.")
    result = run_agent(client, [{"role": "user", "content": "What are total sales?"}])
    assert "51,400" in result


def test_agent_tool_chain():
    client = _mock_tool_then_text(
        "lookup_sales", {"month": "2026-03"}, "March revenue was $51,400."
    )
    result = run_agent(client, [{"role": "user", "content": "Sales in March?"}])
    assert "51,400" in result
    assert client.messages.create.call_count == 2


def test_agent_stops_after_max_rounds():
    """Agent should not loop forever if Claude keeps calling tools."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.id = "t1"
    tool_block.name = "check_inventory"
    tool_block.input = {}

    response = MagicMock()
    response.stop_reason = "tool_use"
    response.content = [tool_block]

    client = MagicMock()
    client.messages.create.return_value = response

    result = run_agent(client, [{"role": "user", "content": "loop"}])
    assert isinstance(result, str)
    assert client.messages.create.call_count == 5  # hits the limit
