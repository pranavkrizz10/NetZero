"""Pydantic schemas (API contract).

Amounts cross the API boundary as rupees (float, 2 dp). Internally everything
is integer paise. Conversion happens in the routers.
"""
from typing import List, Optional, Literal
from pydantic import BaseModel, EmailStr, Field


# ---- auth ----
class RegisterIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    email: EmailStr
    password: str = Field(min_length=4, max_length=200)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    id: int
    name: str
    email: str

    class Config:
        from_attributes = True


class AuthOut(BaseModel):
    token: str
    user: UserOut


# ---- groups ----
class GroupCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AddMemberIn(BaseModel):
    email: EmailStr


class GroupSummary(BaseModel):
    id: int
    name: str
    member_count: int
    your_net: float   # + means you are owed, - means you owe


class MemberBalance(BaseModel):
    user_id: int
    name: str
    net: float        # + owed to them, - they owe


# ---- expenses ----
class ParticipantShareIn(BaseModel):
    user_id: int
    # For split_type == exact: rupees this user owes.
    # For split_type == percent: percentage (0-100) this user owes.
    # Ignored for split_type == equal.
    value: Optional[float] = None


class ExpenseCreateIn(BaseModel):
    description: str = Field(min_length=1, max_length=255)
    amount: float = Field(gt=0)
    paid_by: int
    split_type: Literal["equal", "exact", "percent"] = "equal"
    participants: List[ParticipantShareIn]
    category: Optional[str] = None          # if omitted, the model predicts it


class ShareOut(BaseModel):
    user_id: int
    name: str
    share: float


class ExpenseOut(BaseModel):
    id: int
    description: str
    amount: float
    category: str
    category_source: str
    paid_by: int
    paid_by_name: str
    split_type: str
    shares: List[ShareOut]
    created_at: str


class CategoryUpdateIn(BaseModel):
    category: str


# ---- settlements ----
class SettleIn(BaseModel):
    from_user: int
    to_user: int
    amount: float = Field(gt=0)


class SettlementOut(BaseModel):
    id: int
    from_user: int
    from_name: str
    to_user: int
    to_name: str
    amount: float
    created_at: str


class SimplifiedTransfer(BaseModel):
    from_user: int
    from_name: str
    to_user: int
    to_name: str
    amount: float


class SimplifyOut(BaseModel):
    balances: List[MemberBalance]
    # naive_count: transfers if everyone just paid back each raw debt
    naive_count: int
    # optimized transfers from the simplification engine
    transfers: List[SimplifiedTransfer]
    optimized_count: int


class GroupDetailOut(BaseModel):
    id: int
    name: str
    members: List[UserOut]
    expenses: List[ExpenseOut]
    settlements: List[SettlementOut]
    simplify: SimplifyOut


# ---- ML / NLP ----
class CategorizeIn(BaseModel):
    description: str


class CategorizeOut(BaseModel):
    category: str
    confidence: float


class NLPParseIn(BaseModel):
    text: str


class NLPParseOut(BaseModel):
    """A draft expense parsed from free text. The UI pre-fills the form with
    this and the user confirms before it is saved."""
    ok: bool
    amount: Optional[float] = None
    description: Optional[str] = None
    category: Optional[str] = None
    paid_by: Optional[int] = None
    paid_by_name: Optional[str] = None
    split_type: str = "equal"
    participant_ids: List[int] = []
    participant_names: List[str] = []
    warnings: List[str] = []


class RetrainOut(BaseModel):
    trained_on: int
    new_corrections_folded_in: int
    accuracy_holdout: float
    categories: List[str]
