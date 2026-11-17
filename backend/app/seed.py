"""Seed demo data and train the ML model.

Run from the backend/ directory:
    python -m app.seed

Creates four users (password: 'password' for all), one group with a realistic
tangle of expenses, and trains the categoriser. Idempotent-ish: it wipes and
recreates the demo group each run but leaves other data alone.
"""
from .database import Base, engine, SessionLocal
from . import models, auth
from .services import balances as balance_svc
from .services import categorizer

DEMO_USERS = [
    ("Hari", "hari@demo.com"),
    ("Raj", "raj@demo.com"),
    ("Priya", "priya@demo.com"),
    ("Anjali", "anjali@demo.com"),
]

# (description, amount_rupees, payer_name, [participant_names] or None=all)
DEMO_EXPENSES = [
    ("Hotel booking in Goa", 4000, "Hari", None),
    ("Dinner at beach shack", 2400, "Raj", None),
    ("Cab to airport", 1200, "Priya", None),
    ("Groceries from bigbasket", 800, "Anjali", None),
    ("Movie tickets", 1500, "Hari", ["Hari", "Raj", "Priya"]),
    ("Petrol for scooter", 900, "Raj", ["Raj", "Anjali"]),
    ("Swiggy late night order", 600, "Priya", ["Hari", "Priya"]),
]


def get_or_create_user(db, name, email):
    u = db.query(models.User).filter(models.User.email == email).first()
    if u:
        return u
    u = models.User(name=name, email=email,
                    password_hash=auth.hash_password("password"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def run():
    Base.metadata.create_all(bind=engine)

    # 1) Train the ML model so predictions work immediately.
    print("Training categorisation model...")
    from ml.train import train_model
    report = train_model()
    print(f"  trained on {report['trained_on']} examples, "
          f"holdout acc {report['holdout_accuracy']:.3f}")
    categorizer.reload_model()

    db = SessionLocal()
    try:
        users = {name: get_or_create_user(db, name, email)
                 for name, email in DEMO_USERS}
        id_by_name = {n: u.id for n, u in users.items()}

        # 2) Fresh demo group.
        existing = db.query(models.Group).filter(models.Group.name == "Goa Trip").first()
        if existing:
            db.query(models.ExpenseShare).filter(
                models.ExpenseShare.expense_id.in_(
                    db.query(models.Expense.id).filter(
                        models.Expense.group_id == existing.id)
                )
            ).delete(synchronize_session=False)
            db.query(models.Expense).filter(
                models.Expense.group_id == existing.id).delete()
            db.query(models.Settlement).filter(
                models.Settlement.group_id == existing.id).delete()
            db.query(models.Membership).filter(
                models.Membership.group_id == existing.id).delete()
            db.delete(existing)
            db.commit()

        group = models.Group(name="Goa Trip", created_by=id_by_name["Hari"])
        db.add(group)
        db.commit()
        db.refresh(group)
        for uid in id_by_name.values():
            db.add(models.Membership(group_id=group.id, user_id=uid))
        db.commit()

        # 3) Expenses (category predicted by the model — shows it working).
        for desc, amount, payer, participants in DEMO_EXPENSES:
            names = participants or list(id_by_name.keys())
            part_ids = [id_by_name[n] for n in names]
            amount_paise = int(round(amount * 100))
            shares = balance_svc.equal_split(amount_paise, part_ids)
            category, _ = categorizer.predict(desc)
            exp = models.Expense(
                group_id=group.id, description=desc, amount_paise=amount_paise,
                category=category, category_source="model",
                paid_by=id_by_name[payer], split_type="equal",
            )
            db.add(exp)
            db.flush()
            for uid, paise in shares.items():
                db.add(models.ExpenseShare(expense_id=exp.id, user_id=uid,
                                           share_paise=paise))
        db.commit()

        # 4) Show the resulting settlement plan in the console.
        from .services import simplify as simplify_svc
        net, raw_edges = balance_svc.group_balances(db, group.id)
        transfers = simplify_svc.simplify(dict(net))
        name_by_id = {u.id: n for n, u in users.items()}
        print(f"\nDemo group 'Goa Trip' created with {len(DEMO_EXPENSES)} expenses.")
        print(f"Raw debt edges (naive): {raw_edges}")
        print(f"Simplified into {len(transfers)} payments:")
        for fu, tu, amt in transfers:
            print(f"  {name_by_id[fu]:>6}  ->  {name_by_id[tu]:<6}  ₹{amt/100:,.2f}")
        print("\nLogin with any of: hari@demo.com / raj@demo.com / "
              "priya@demo.com / anjali@demo.com  (password: password)")
    finally:
        db.close()


if __name__ == "__main__":
    run()
