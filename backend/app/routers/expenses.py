from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_membership
from .. import models, schemas
from ..services import balances as balance_svc
from ..services import categorizer, serializers

router = APIRouter(prefix="/api", tags=["expenses"])


def _compute_shares(body: schemas.ExpenseCreateIn, amount_paise: int) -> dict:
    """Return {user_id: share_paise} that sums exactly to amount_paise."""
    part_ids = [p.user_id for p in body.participants]
    if not part_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Need at least one participant")

    if body.split_type == "equal":
        return balance_svc.equal_split(amount_paise, part_ids)

    if body.split_type == "exact":
        shares = {}
        total = 0
        for p in body.participants:
            if p.value is None:
                raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                    "Exact split needs an amount for each participant")
            paise = serializers.rupees_to_paise(p.value)
            shares[p.user_id] = paise
            total += paise
        if total != amount_paise:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Exact shares (₹{total/100:.2f}) must sum to the total (₹{amount_paise/100:.2f})",
            )
        return shares

    if body.split_type == "percent":
        pct_total = sum((p.value or 0) for p in body.participants)
        if abs(pct_total - 100) > 0.01:
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                f"Percentages must add up to 100 (got {pct_total})")
        shares = {}
        assigned = 0
        ordered = sorted(body.participants, key=lambda p: p.user_id)
        for i, p in enumerate(ordered):
            if i == len(ordered) - 1:
                shares[p.user_id] = amount_paise - assigned  # last takes remainder
            else:
                paise = int(round(amount_paise * (p.value or 0) / 100))
                shares[p.user_id] = paise
                assigned += paise
        return shares

    raise HTTPException(status.HTTP_400_BAD_REQUEST, "Unknown split type")


@router.post("/groups/{group_id}/expenses", response_model=schemas.ExpenseOut)
def create_expense(
    group_id: int,
    body: schemas.ExpenseCreateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    require_membership(db, group_id, user.id)

    # Validate everyone involved is a member.
    member_ids = {
        m.user_id for m in
        db.query(models.Membership).filter(models.Membership.group_id == group_id).all()
    }
    involved = {body.paid_by} | {p.user_id for p in body.participants}
    if not involved <= member_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "Payer and participants must all be group members")

    amount_paise = serializers.rupees_to_paise(body.amount)
    shares = _compute_shares(body, amount_paise)

    # Auto-categorise when the client didn't set a category.
    if body.category:
        category, source = body.category, "user"
    else:
        category, _conf = categorizer.predict(body.description)
        source = "model"

    exp = models.Expense(
        group_id=group_id,
        description=body.description.strip(),
        amount_paise=amount_paise,
        category=category,
        category_source=source,
        paid_by=body.paid_by,
        split_type=body.split_type,
    )
    db.add(exp)
    db.flush()
    for uid, paise in shares.items():
        db.add(models.ExpenseShare(expense_id=exp.id, user_id=uid, share_paise=paise))
    db.commit()
    db.refresh(exp)

    name_by_id = serializers.name_map(db, group_id)
    return serializers.expense_out(exp, name_by_id)


@router.delete("/expenses/{expense_id}")
def delete_expense(
    expense_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    exp = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    require_membership(db, exp.group_id, user.id)
    db.delete(exp)
    db.commit()
    return {"deleted": expense_id}


@router.put("/expenses/{expense_id}/category", response_model=schemas.ExpenseOut)
def correct_category(
    expense_id: int,
    body: schemas.CategoryUpdateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    """User overrides the category. This is logged as a training correction so
    the model can learn from it on the next retrain — the feedback loop."""
    exp = db.query(models.Expense).filter(models.Expense.id == expense_id).first()
    if not exp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expense not found")
    require_membership(db, exp.group_id, user.id)

    changed = exp.category != body.category
    exp.category = body.category
    exp.category_source = "user"
    if changed:
        db.add(models.CategoryCorrection(
            description=exp.description, category=body.category
        ))
    db.commit()
    db.refresh(exp)
    name_by_id = serializers.name_map(db, exp.group_id)
    return serializers.expense_out(exp, name_by_id)
