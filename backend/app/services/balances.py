"""Compute per-member net balances for a group, in integer paise.

net[user] = (everything the user paid) - (the user's share of everything)
            + (settlements they paid out) - (settlements paid to them)

A settlement from A to B means A handed B real cash, which reduces A's debt
(pushes A's net up toward zero) and reduces what B is owed (pushes B down).
By construction the nets always sum to exactly zero.
"""
from typing import Dict, Tuple, List

from sqlalchemy.orm import Session

from .. import models


def group_balances(db: Session, group_id: int) -> Tuple[Dict[int, int], int]:
    """Return ({user_id: net_paise}, raw_debt_edge_count).

    raw_debt_edge_count is how many (debtor -> payer) obligations exist across
    all expenses before any netting — the baseline the simplifier improves on.
    """
    members = (
        db.query(models.Membership)
        .filter(models.Membership.group_id == group_id)
        .all()
    )
    net: Dict[int, int] = {m.user_id: 0 for m in members}

    expenses = (
        db.query(models.Expense)
        .filter(models.Expense.group_id == group_id)
        .all()
    )
    raw_edges = 0
    for exp in expenses:
        net.setdefault(exp.paid_by, 0)
        net[exp.paid_by] += exp.amount_paise
        for share in exp.shares:
            net.setdefault(share.user_id, 0)
            net[share.user_id] -= share.share_paise
            # An edge exists whenever a non-payer owes a positive share.
            if share.user_id != exp.paid_by and share.share_paise > 0:
                raw_edges += 1

    settlements = (
        db.query(models.Settlement)
        .filter(models.Settlement.group_id == group_id)
        .all()
    )
    for s in settlements:
        net.setdefault(s.from_user, 0)
        net.setdefault(s.to_user, 0)
        net[s.from_user] += s.amount_paise   # paid out -> debt reduced
        net[s.to_user] -= s.amount_paise     # received -> owed reduced

    return net, raw_edges


def equal_split(amount_paise: int, user_ids: List[int]) -> Dict[int, int]:
    """Split an amount equally, distributing the remainder paise deterministically
    so the shares sum to exactly the total (no lost/created paise)."""
    n = len(user_ids)
    base = amount_paise // n
    remainder = amount_paise - base * n
    shares = {}
    for i, uid in enumerate(sorted(user_ids)):
        shares[uid] = base + (1 if i < remainder else 0)
    return shares
