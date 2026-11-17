# NetZero — a smart shared-expense splitter

NetZero lets a group log shared expenses and then **settle up in the fewest
possible payments**. Instead of everyone paying back every individual debt, it
nets everyone's balance and produces the minimum set of transfers that clears
the group — the "net to zero" idea the name comes from.

It adds two assistive ML features on top of the core:

- **Auto-categorisation** — expenses are tagged (Food, Transport, Rent…) by a
  trained text classifier, and it **learns from your corrections**.
- **Natural-language entry** — type *"I paid 1200 for dinner with Raj and Priya,
  split equally"* and it fills in the expense for you.

> Built as a software-engineering course project. Backend: FastAPI + SQLite.
> Frontend: a no-build vanilla-JS single-page app served by the same server.
> ML: scikit-learn.

---

## Quick start

You need **Python 3.10+**. From the project root:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# create demo data + train the categoriser (one time)
python -m app.seed

# run it
uvicorn app.main:app --reload
```

Now open **http://localhost:8000** in your browser.

**Demo logins** (password is `password` for all):
`hari@demo.com` · `raj@demo.com` · `priya@demo.com` · `anjali@demo.com`

The seeded "Goa Trip" group has a tangle of 7 expenses that the engine
collapses from **16 raw debts into just 3 payments** — a good thing to open
your demo with.

### Run the tests

```bash
cd backend
python -m pytest        # 98 tests, incl. property tests on the settle engine
```

---

## What each feature does

| Feature | Where | Notes |
|---|---|---|
| Groups, members, expenses | `routers/groups.py`, `routers/expenses.py` | multi-role: any member can add expenses |
| Equal / exact / percentage splits | `routers/expenses.py`, `services/balances.py` | remainder paise distributed so shares sum exactly |
| **Debt simplification (the core)** | `services/simplify.py` | minimum-payment settle-up |
| Record settlements | `routers/settlements.py` | logging a real payment updates balances |
| **Auto-categorisation** | `services/categorizer.py`, `ml/` | TF-IDF + LogisticRegression |
| **Correction → retrain loop** | `routers/ml.py`, `routers/expenses.py` | overrides become training data |
| **Natural-language entry** | `services/nlp_parser.py` | rule-based information extraction |

---

## Architecture

```
Browser (vanilla JS SPA)
      │  fetch() JSON
      ▼
FastAPI  ── routers ──►  services ──►  SQLAlchemy ──►  SQLite
                          │
                          ├─ simplify.py     (settlement algorithm)
                          ├─ balances.py     (net balances, in paise)
                          ├─ categorizer.py  ─► ml/model.joblib
                          └─ nlp_parser.py
```

- **Money is stored and computed in integer paise** everywhere, and only
  converted to rupees at the API edge. A settlement engine has to balance to
  *exactly* zero — integers make that guaranteed instead of hoping floats
  behave.
- **Services are pure and unit-testable** (`simplify` and `balances` don't touch
  the DB or FastAPI), which is why the core has real property tests.
- The **ML features sit off the critical path**: a wrong prediction is just
  corrected in the form, so a flaky model can never block or break settling up.

See [`docs/DESIGN.md`](docs/DESIGN.md) for the data model, the algorithm's
theory (including why exact minimisation is NP-hard), and the request flows.

---

## The core: debt simplification

After expenses, each member has a net balance (＋owed / −owes) that sums to
zero. A naive settle-up makes one payment per debt; NetZero nets them down.

The provably-minimum number of payments is **NP-hard** (it's a zero-sum subset
partition problem). NetZero ships the standard practical approach:

1. A **greedy max-cash-flow** heuristic: repeatedly settle the biggest creditor
   against the biggest debtor. Always ≤ n−1 payments.
2. For small groups (≤ 15 members) an **exact optimisation** first carves the
   members into zero-sum subgroups, which provably does at least as well as
   plain greedy.

The property tests in `tests/test_simplify.py` assert the invariants any valid
plan must satisfy (clears every balance, ≤ n−1 transfers, conserves total debt,
no self-payments) and fuzz them across 80 random groups.

---

## The ML: categorisation that learns

`ml/train.py` builds a **TF-IDF (word + character n-grams) → Logistic
Regression** pipeline. Character n-grams make it robust to typos and unseen
merchants (`"grocries from dmart"` still lands on Groceries). It's seeded from a
hand-written dataset (`ml/training_data.py`) and reports **~0.79 stratified
cross-validation accuracy**.

The feedback loop: when you press **fix** on a category, the correction is
logged. `POST /api/ml/retrain` folds all corrections back into the training set,
retrains, and hot-reloads the model — so it adapts to how *your* group writes
expenses.

---

## The NLP: natural-language entry

`services/nlp_parser.py` is honest **rule-based information extraction**, not a
learned parser: regex for the amount (handles `₹`, `rs`, `1.2k`), keyword
detection for who paid and how it's split, and dictionary matching of names
against the group's actual roster. That roster grounding is what makes it
reliable — it only resolves names it can see. The extracted description is then
sent through the ML categoriser. It returns a **draft** the user confirms, so a
mis-parse is always correctable.

---

## API reference (short)

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/auth/register` · `/login` | accounts + bearer token |
| GET | `/api/groups` | your groups + your net in each |
| POST | `/api/groups` | create a group |
| POST | `/api/groups/{id}/members` | add a member by email |
| GET | `/api/groups/{id}` | full detail incl. the simplify plan |
| GET | `/api/groups/{id}/simplify` | just the settle-up plan |
| POST | `/api/groups/{id}/expenses` | add expense (auto-categorised) |
| PUT | `/api/expenses/{id}/category` | correct a category (feeds retrain) |
| DELETE | `/api/expenses/{id}` | remove an expense |
| POST | `/api/groups/{id}/settle` | record a payment |
| POST | `/api/groups/{id}/nlp-parse` | parse free-text into a draft |
| POST | `/api/ml/categorize` | predict a category |
| POST | `/api/ml/retrain` | fold corrections in and retrain |

Interactive docs (Swagger) are auto-generated at
**http://localhost:8000/docs** when the server is running.

---

## Project structure

```
netzero/
├── README.md
├── backend/
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/
│   │   ├── main.py            FastAPI app + static frontend mount
│   │   ├── database.py        engine/session (SQLite)
│   │   ├── models.py          ORM models (money in paise)
│   │   ├── schemas.py         Pydantic API contract
│   │   ├── auth.py            password hashing + tokens
│   │   ├── deps.py            auth / membership dependencies
│   │   ├── seed.py            demo data + model training
│   │   ├── routers/           auth, groups, expenses, settlements, ml
│   │   └── services/          simplify, balances, categorizer, nlp_parser, serializers
│   ├── ml/
│   │   ├── training_data.py   bootstrap dataset
│   │   └── train.py           training / retraining pipeline
│   └── tests/                 test_simplify, test_balances, test_nlp
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   └── js/  api.js · app.js
└── docs/DESIGN.md
```

---

## Notes / limitations

- Auth uses opaque DB-stored bearer tokens — simple and revocable; swap in JWT
  if you want stateless sessions.
- SQLite is used for zero-setup portability; the code is plain SQLAlchemy, so
  moving to PostgreSQL is a one-line URL change in `database.py`.
- The NLP path supports equal splits; exact/percentage splits are entered via
  the manual form.
