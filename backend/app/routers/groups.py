from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_membership
from .. import models, schemas
from ..services import serializers, balances as balance_svc

router = APIRouter(prefix="/api/groups", tags=["groups"])


@router.post("", response_model=schemas.GroupSummary)
def create_group(
    body: schemas.GroupCreateIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    group = models.Group(name=body.name.strip(), created_by=user.id)
    db.add(group)
    db.commit()
    db.refresh(group)
    db.add(models.Membership(group_id=group.id, user_id=user.id))
    db.commit()
    return {"id": group.id, "name": group.name, "member_count": 1, "your_net": 0.0}


@router.get("", response_model=list[schemas.GroupSummary])
def list_groups(
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    memberships = (
        db.query(models.Membership)
        .filter(models.Membership.user_id == user.id)
        .all()
    )
    out = []
    for m in memberships:
        group = db.query(models.Group).filter(models.Group.id == m.group_id).first()
        if not group:
            continue
        member_count = (
            db.query(models.Membership)
            .filter(models.Membership.group_id == group.id)
            .count()
        )
        net, _ = balance_svc.group_balances(db, group.id)
        out.append({
            "id": group.id,
            "name": group.name,
            "member_count": member_count,
            "your_net": serializers.paise_to_rupees(net.get(user.id, 0)),
        })
    return out


@router.post("/{group_id}/members", response_model=list[schemas.UserOut])
def add_member(
    group_id: int,
    body: schemas.AddMemberIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    require_membership(db, group_id, user.id)
    target = db.query(models.User).filter(models.User.email == body.email.lower()).first()
    if not target:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No user with that email — ask them to sign up first")
    exists = (
        db.query(models.Membership)
        .filter(models.Membership.group_id == group_id,
                models.Membership.user_id == target.id)
        .first()
    )
    if not exists:
        db.add(models.Membership(group_id=group_id, user_id=target.id))
        db.commit()
    members = (
        db.query(models.User)
        .join(models.Membership, models.Membership.user_id == models.User.id)
        .filter(models.Membership.group_id == group_id)
        .all()
    )
    return members


@router.get("/{group_id}", response_model=schemas.GroupDetailOut)
def group_detail(
    group_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    require_membership(db, group_id, user.id)
    group = db.query(models.Group).filter(models.Group.id == group_id).first()
    if not group:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Group not found")

    name_by_id = serializers.name_map(db, group_id)
    members = (
        db.query(models.User)
        .join(models.Membership, models.Membership.user_id == models.User.id)
        .filter(models.Membership.group_id == group_id)
        .all()
    )
    expenses = (
        db.query(models.Expense)
        .filter(models.Expense.group_id == group_id)
        .order_by(models.Expense.created_at.desc())
        .all()
    )
    settlements = (
        db.query(models.Settlement)
        .filter(models.Settlement.group_id == group_id)
        .order_by(models.Settlement.created_at.desc())
        .all()
    )
    return {
        "id": group.id,
        "name": group.name,
        "members": members,
        "expenses": [serializers.expense_out(e, name_by_id) for e in expenses],
        "settlements": [serializers.settlement_out(s, name_by_id) for s in settlements],
        "simplify": serializers.simplify_out(db, group_id, name_by_id),
    }


@router.get("/{group_id}/simplify", response_model=schemas.SimplifyOut)
def simplify(
    group_id: int,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    require_membership(db, group_id, user.id)
    name_by_id = serializers.name_map(db, group_id)
    return serializers.simplify_out(db, group_id, name_by_id)
