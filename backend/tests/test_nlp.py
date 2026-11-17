"""Tests for the natural-language expense parser."""
from app.services.nlp_parser import parse

MEMBERS = [
    {"id": 1, "name": "Hari"},
    {"id": 2, "name": "Raj"},
    {"id": 3, "name": "Priya"},
    {"id": 4, "name": "Anjali"},
]
ME = 1  # Hari is typing


def test_full_sentence():
    r = parse("I paid 1200 for dinner with Raj and Priya, split equally", MEMBERS, ME)
    assert r["ok"]
    assert r["amount"] == 1200
    assert r["paid_by"] == ME
    assert set(r["participant_ids"]) == {1, 2, 3}  # me + Raj + Priya
    assert "dinner" in r["description"].lower()
    assert r["split_type"] == "equal"


def test_currency_symbol():
    r = parse("₹450 auto rickshaw", MEMBERS, ME)
    assert r["amount"] == 450
    assert r["category"] == "Transport"


def test_k_suffix():
    r = parse("2k for hotel booking split with everyone", MEMBERS, ME)
    assert r["amount"] == 2000
    assert set(r["participant_ids"]) == {1, 2, 3, 4}


def test_other_person_paid():
    r = parse("Raj paid 600 for groceries", MEMBERS, ME)
    assert r["paid_by"] == 2  # Raj


def test_no_amount_flags_not_ok():
    r = parse("dinner with Raj", MEMBERS, ME)
    assert not r["ok"]
    assert any("amount" in w.lower() for w in r["warnings"])


def test_no_names_defaults_to_group():
    r = parse("paid 800 for pizza", MEMBERS, ME)
    assert set(r["participant_ids"]) == {1, 2, 3, 4}
    assert any("whole group" in w.lower() for w in r["warnings"])


def test_rs_prefix_and_category():
    r = parse("rs 300 movie tickets with Anjali", MEMBERS, ME)
    assert r["amount"] == 300
    assert r["category"] == "Entertainment"
    assert set(r["participant_ids"]) == {1, 4}
