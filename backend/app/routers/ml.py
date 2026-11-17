from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import current_user, require_membership
from .. import models, schemas
from ..services import categorizer, nlp_parser

# ml.train is imported lazily inside retrain to keep import graph light.

router = APIRouter(prefix="/api", tags=["ml"])


@router.post("/ml/categorize", response_model=schemas.CategorizeOut)
def categorize(body: schemas.CategorizeIn, user: models.User = Depends(current_user)):
    category, confidence = categorizer.predict(body.description)
    return {"category": category, "confidence": round(confidence, 3)}


@router.post("/groups/{group_id}/nlp-parse", response_model=schemas.NLPParseOut)
def nlp_parse(
    group_id: int,
    body: schemas.NLPParseIn,
    db: Session = Depends(get_db),
    user: models.User = Depends(current_user),
):
    require_membership(db, group_id, user.id)
    members = [
        {"id": u.id, "name": u.name}
        for u in (
            db.query(models.User)
            .join(models.Membership, models.Membership.user_id == models.User.id)
            .filter(models.Membership.group_id == group_id)
            .all()
        )
    ]
    return nlp_parser.parse(body.text, members, user.id)


@router.post("/ml/retrain", response_model=schemas.RetrainOut)
def retrain(db: Session = Depends(get_db), user: models.User = Depends(current_user)):
    """Fold all logged user corrections into the training set, retrain, and
    hot-reload the model. This is the 'learns from feedback' loop made explicit.
    """
    from ml.train import train_model  # lazy import

    corrections = (
        db.query(models.CategoryCorrection)
        .filter(models.CategoryCorrection.used_in_training == False)  # noqa: E712
        .all()
    )
    extra = [(c.description, c.category) for c in corrections]
    report = train_model(extra=extra)

    for c in corrections:
        c.used_in_training = True
    db.commit()

    categorizer.reload_model()
    return {
        "trained_on": report["trained_on"],
        "new_corrections_folded_in": report["extra_folded_in"],
        "accuracy_holdout": round(report["holdout_accuracy"], 3),
        "categories": report["categories"],
    }
