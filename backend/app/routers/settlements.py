from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_membership
from .. import models, schemas
from ..services import serializers

router = APIRouter(prefix="/api", tags=["settlements"])


@router.post("/groups/{group_id}/settle", response_model=schemas.SettlementOut)
def settle(
    group_id: int,
    body: schemas.SettleIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    require_membership(db, group_id, user.id)
    if body.from_user == body.to_user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Payer and payee can't be the same")

    member_ids = {
        m.user_id for m in
        db.query(models.Membership).filter(models.Membership.group_id == group_id).all()
    }
    if body.from_user not in member_ids or body.to_user not in member_ids:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Both parties must be group members")

    s = models.Settlement(
        group_id=group_id,
        from_user=body.from_user,
        to_user=body.to_user,
        amount_paise=serializers.rupees_to_paise(body.amount),
    )
    db.add(s)
    db.commit()
    db.refresh(s)
    name_by_id = serializers.name_map(db, group_id)
    return serializers.settlement_out(s, name_by_id)
