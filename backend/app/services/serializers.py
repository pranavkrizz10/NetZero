"""Turn ORM objects + computed balances into API response dicts.

Keeps money conversion (paise -> rupees) in one place.
"""
from typing import Dict, List

from sqlalchemy.orm import Session

from .. import models
from . import balances as balance_svc
from . import simplify as simplify_svc


def paise_to_rupees(p: int) -> float:
    return round(p / 100, 2)


def rupees_to_paise(r: float) -> int:
    return int(round(r * 100))


def expense_out(exp: models.Expense, name_by_id: Dict[int, str]) -> dict:
    return {
        "id": exp.id,
        "description": exp.description,
        "amount": paise_to_rupees(exp.amount_paise),
        "category": exp.category,
        "category_source": exp.category_source,
        "paid_by": exp.paid_by,
        "paid_by_name": name_by_id.get(exp.paid_by, "?"),
        "split_type": exp.split_type,
        "shares": [
            {
                "user_id": s.user_id,
                "name": name_by_id.get(s.user_id, "?"),
                "share": paise_to_rupees(s.share_paise),
            }
            for s in exp.shares
        ],
        "created_at": exp.created_at.isoformat() if exp.created_at else "",
    }


def settlement_out(s: models.Settlement, name_by_id: Dict[int, str]) -> dict:
    return {
        "id": s.id,
        "from_user": s.from_user,
        "from_name": name_by_id.get(s.from_user, "?"),
        "to_user": s.to_user,
        "to_name": name_by_id.get(s.to_user, "?"),
        "amount": paise_to_rupees(s.amount_paise),
        "created_at": s.created_at.isoformat() if s.created_at else "",
    }


def simplify_out(db: Session, group_id: int, name_by_id: Dict[int, str]) -> dict:
    net, raw_edges = balance_svc.group_balances(db, group_id)
    transfers = simplify_svc.simplify(dict(net))

    balances_list = [
        {"user_id": uid, "name": name_by_id.get(uid, "?"),
         "net": paise_to_rupees(bal)}
        for uid, bal in sorted(net.items(), key=lambda kv: -kv[1])
    ]
    transfers_out = [
        {
            "from_user": fu, "from_name": name_by_id.get(fu, "?"),
            "to_user": tu, "to_name": name_by_id.get(tu, "?"),
            "amount": paise_to_rupees(amt),
        }
        for (fu, tu, amt) in transfers
    ]
    return {
        "balances": balances_list,
        "naive_count": raw_edges,
        "transfers": transfers_out,
        "optimized_count": len(transfers_out),
    }


def name_map(db: Session, group_id: int) -> Dict[int, str]:
    rows = (
        db.query(models.User)
        .join(models.Membership, models.Membership.user_id == models.User.id)
        .filter(models.Membership.group_id == group_id)
        .all()
    )
    return {u.id: u.name for u in rows}
