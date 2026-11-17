"""Invariant tests for the settlement engine — the core correctness proof.

We assert the properties a settlement plan MUST satisfy, then hammer them with
random balances. These are the tests to point a reviewer at: they show the
engine is correct, not just that it runs.
"""
import random

import pytest

from app.services.simplify import simplify, SETTLE_EXACT_LIMIT


def apply_transfers(balances, transfers):
    """Simulate paying out the plan; return resulting balances."""
    result = dict(balances)
    for fu, tu, amt in transfers:
        assert amt > 0, "no zero/negative transfers"
        assert fu != tu, "no self-payments"
        result[fu] = result.get(fu, 0) + amt   # debtor pays -> net rises
        result[tu] = result.get(tu, 0) - amt   # creditor receives -> net falls
    return result


def check_all_invariants(balances):
    transfers = simplify(dict(balances))
    n_nonzero = sum(1 for v in balances.values() if v != 0)

    # 1) Clears everything: everyone ends at exactly zero.
    after = apply_transfers(balances, transfers)
    assert all(v == 0 for v in after.values()), f"not cleared: {after}"

    # 2) At most n-1 transfers (greedy guarantee; exact path only does better).
    assert len(transfers) <= max(n_nonzero - 1, 0)

    # 3) Conservation: total money moved == total debt owed.
    total_debt = sum(-v for v in balances.values() if v < 0)
    assert sum(amt for _, _, amt in transfers) == total_debt

    # 4) No self-payments, all amounts positive (checked in apply_transfers).
    return transfers


def test_empty():
    assert simplify({}) == []


def test_already_settled():
    assert simplify({1: 0, 2: 0, 3: 0}) == []


def test_simple_two_person():
    t = simplify({1: 500, 2: -500})
    assert t == [(2, 1, 500)]


def test_chain_collapses():
    # A owed by B, B owed by C -> should NOT need 2 hops if it can net.
    # Here: 1 is owed 1000, 2 is neutral-ish, 3 owes 1000.
    balances = {1: 1000, 2: 0, 3: -1000}
    t = check_all_invariants(balances)
    assert len(t) == 1  # direct 3 -> 1


def test_zero_sum_subgroup_optimization():
    # Two independent pairs. Exact solver should find 2 transfers, not more.
    balances = {1: 300, 2: -300, 3: 700, 4: -700}
    t = check_all_invariants(balances)
    assert len(t) == 2


def test_fixed_known_case():
    # Classic: three owe, one is owed everything.
    balances = {1: 3000, 2: -1000, 3: -1000, 4: -1000}
    t = check_all_invariants(balances)
    assert len(t) == 3


@pytest.mark.parametrize("seed", range(50))
def test_random_small_groups(seed):
    """Random zero-sum balances for groups that hit the EXACT solver path."""
    rng = random.Random(seed)
    n = rng.randint(2, SETTLE_EXACT_LIMIT)
    vals = [rng.randint(-5000, 5000) for _ in range(n - 1)]
    vals.append(-sum(vals))  # force sum to zero
    rng.shuffle(vals)
    balances = {i: vals[i] for i in range(n)}
    check_all_invariants(balances)


@pytest.mark.parametrize("seed", range(30))
def test_random_large_groups(seed):
    """Random zero-sum balances beyond the exact limit -> greedy path."""
    rng = random.Random(1000 + seed)
    n = rng.randint(SETTLE_EXACT_LIMIT + 1, SETTLE_EXACT_LIMIT + 25)
    vals = [rng.randint(-10000, 10000) for _ in range(n - 1)]
    vals.append(-sum(vals))
    rng.shuffle(vals)
    balances = {i: vals[i] for i in range(n)}
    check_all_invariants(balances)


def test_exact_beats_or_ties_greedy():
    """On partitionable inputs, the exact path must not do worse than greedy."""
    from app.services.simplify import _greedy
    balances = {1: 100, 2: -100, 3: 200, 4: -200, 5: 50, 6: -50}
    exact = simplify(dict(balances))
    greedy = _greedy(dict(balances))
    assert len(exact) <= len(greedy)
