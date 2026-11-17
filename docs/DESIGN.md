# NetZero — Design Document

This document covers the data model, the settlement algorithm (with its
complexity analysis), and the key request flows. It's aimed at a reviewer who
wants to understand *why* the system is built the way it is, not just what it
does.

---

## 1. Requirements (what the system must do)

**Functional**

- Users register, log in, and belong to one or more groups.
- Any member can add an expense: who paid, how much, who shares it, and how
  it's split (equally, by exact amounts, or by percentage).
- The system computes each member's net balance in a group.
- The system produces a **minimal set of payments** that settles the group.
- Members can record real payments (settlements), which update balances.
- Expenses are auto-categorised, and users can correct the category.
- Expenses can be entered in natural language.

**Non-functional**

- Correctness of money math is paramount — balances must net to exactly zero.
- ML features must never block the core flow (graceful degradation).
- Runs with one command and no external services (SQLite, no build step).

---

## 2. Data model

```
users (id, name, email, password_hash, created_at)
groups (id, name, created_by → users.id, created_at)
memberships (id, group_id → groups.id, user_id → users.id)     # M:N
expenses (id, group_id, description, amount_paise, category,
          category_source, paid_by → users.id, split_type, created_at)
expense_shares (id, expense_id → expenses.id, user_id, share_paise)
settlements (id, group_id, from_user, to_user, amount_paise, created_at)
tokens (id, token, user_id → users.id)                          # bearer auth
category_corrections (id, description, category, used_in_training)  # ML feedback
```

Relationships:

```
User ──< Membership >── Group ──< Expense ──< ExpenseShare
                          │
                          └──< Settlement
```

**Design decision — money as integer paise.** Every amount that gets summed,
split, or netted is an integer number of paise. Floating-point rupees would
accumulate rounding error and a settlement plan could end up off by a fraction
of a paisa, which then fails the "nets to zero" invariant. Rupees exist only in
the API layer (`serializers.py` converts at the boundary).

**Design decision — `category_source`.** Records whether a category came from
the model (`"model"`) or a human (`"user"`). This drives the ✨ badge in the UI
and separates trusted labels from guesses.

---

## 3. The settlement algorithm

### 3.1 Net balances

For a group, for each expense: the payer's net rises by the full amount; each
participant's net falls by their share. Settlements move net between the two
parties. By construction the nets always sum to zero. (`services/balances.py`)

### 3.2 The problem

Given nets that sum to zero, output the **fewest** transfers that make everyone
zero.

### 3.3 Complexity — why we don't brute-force the true minimum

The minimum number of transfers equals *n − (maximum number of disjoint
zero-sum subgroups)*: a zero-sum subgroup of size k can always be settled in
k−1 transfers, so more subgroups ⇒ fewer transfers. Finding that maximum
partition is **NP-hard** — it's a variant of the subset-sum / partition family.
So an exact solver is exponential in the worst case.

### 3.4 What we ship

1. **Greedy max-cash-flow** (`_greedy`). Repeatedly match the largest creditor
   with the largest debtor (two heaps) and settle the smaller amount. Each step
   zeroes at least one person ⇒ **≤ n − 1 transfers**, and it's optimal or
   near-optimal in practice. This is what real apps use.

2. **Exact optimisation for small groups** (`_zero_sum_subsets`, used when
   n ≤ 15). Search over subsets to carve the members into the maximum number of
   zero-sum subgroups, then greedily settle each. This provably ties or beats
   plain greedy, and stays fast because the group is small (2¹⁵ submasks is
   instant). Test `test_exact_beats_or_ties_greedy` asserts this relationship.

### 3.5 Correctness — the invariants we test

`tests/test_simplify.py` asserts that any produced plan:

- clears every balance to exactly zero (simulated by applying the transfers),
- uses ≤ n − 1 transfers,
- moves a total equal to the total debt (conservation),
- contains no self-payments and no zero/negative amounts,

and fuzzes these across 50 random small groups (exact path) + 30 random large
groups (greedy path). These property tests are the correctness argument.

---

## 4. ML categorisation

**Pipeline** (`ml/train.py`): `FeatureUnion(word 1–2-grams, char_wb 3–5-grams)
→ LogisticRegression`. Word grams learn whole tokens (`uber`, `movie tickets`);
character grams capture subword signal and survive typos and unseen merchants.

**Bootstrap + feedback.** The model starts from a hand-written dataset
(`ml/training_data.py`, ~240 rows, 9 categories, ~0.79 stratified-CV accuracy).
Corrections logged in `category_corrections` are folded back in by
`POST /api/ml/retrain`, which retrains and hot-reloads the model.

**Off the critical path.** `categorizer.predict` is only ever advisory; if the
model file is missing it cold-starts by training on the bootstrap set, so the
app never hard-fails on a missing artifact.

---

## 5. Key flows

### 5.1 Natural-language expense entry

```
user types text
  → POST /api/groups/{id}/nlp-parse
      nlp_parser.parse(text, members, current_user):
        · regex extract amount (₹ / rs / 1.2k)
        · detect payer ("<name> paid" else the current user)
        · match participant names against the group roster
        · detect split keywords
        · reconstruct the description
        · categorizer.predict(description)
  → returns a DRAFT (+ warnings)
  → UI pre-fills the manual form; user confirms
  → POST /api/groups/{id}/expenses  (normal create path)
```

The parse step never writes anything — it only proposes. This keeps a
mis-parse harmless.

### 5.2 Add expense + auto-categorise

```
POST /api/groups/{id}/expenses
  · validate payer + participants are members
  · compute shares (equal / exact / percent) so they sum to the total
  · if no category supplied → categorizer.predict(); source = "model"
  · persist expense + shares
```

### 5.3 Correct a category (feedback loop)

```
PUT /api/expenses/{id}/category
  · update the expense category, mark source = "user"
  · if the value actually changed → log a CategoryCorrection
POST /api/ml/retrain
  · pull unused corrections, retrain on bootstrap + corrections
  · mark them used, hot-reload the model
```

---

## 6. Trade-offs and future work

- **Auth**: opaque DB tokens (simple, revocable) over JWT (stateless). Either is
  fine for this scale.
- **DB**: SQLite for portability; plain SQLAlchemy means PostgreSQL is a URL
  swap.
- **NLP** handles equal splits; exact/percentage go through the manual form.
- **Possible extensions**: receipt-OCR entry (reuses the same draft-confirm
  flow), multi-currency, recurring expenses, and an approval step before a
  settlement is marked paid.
