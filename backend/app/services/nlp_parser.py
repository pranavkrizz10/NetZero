"""Natural-language expense entry (rule-based information extraction).

Turns "I paid 1200 for dinner with Raj and Priya, split equally" into a
structured draft:
    {amount: 1200, description: "Dinner", paid_by: <me>,
     participants: [me, Raj, Priya], split_type: "equal",
     category: "Food & Dining"}

This is honest rule-based IE, not a learned parser: regex for amounts, keyword
detection for the payer and split style, and dictionary matching of names
against the actual group roster. That roster grounding is what makes it
reliable — we only ever resolve names we can see in the group. The category is
then filled by the ML categoriser on the extracted description.

It returns a *draft* plus warnings; the UI pre-fills the form and the user
confirms before anything is saved, so a mis-parse is always correctable.
"""
import re
from typing import Dict, List

from . import categorizer

# ---- amount extraction ----
_CURRENCY = r"(?:rs\.?|inr|₹|rupees?)"
_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_AMOUNT_PATTERNS = [
    re.compile(_CURRENCY + r"\s*" + _NUM, re.I),          # rs 1200 / ₹1200
    re.compile(_NUM + r"\s*(k)\b", re.I),                  # 1.2k
    re.compile(_NUM + r"\s*" + _CURRENCY, re.I),          # 1200 rupees
    re.compile(r"\b" + _NUM + r"\b"),                      # bare 1200
]

_PAYER_VERB = r"(?:paid|spent|bought|covered)"
_SPLIT_WORDS = ("equally", "evenly", "split", "50-50", "50/50", "share", "shared")
_EVERYONE_WORDS = ("everyone", "all of us", "whole group", "the group", "all")
_SELF_WORDS = ("me", "myself", "i")

# words we strip when reconstructing the description
_STOP = set("""
i me my myself we us paid pay spent spend bought buy covered for with and to
between among split share shared equally evenly the a an of on at rs inr rupees
rupee everyone all owe owes each other bill amount ₹
""".split())


def _extract_amount(text: str):
    for pat in _AMOUNT_PATTERNS:
        m = pat.search(text)
        if m:
            raw = m.group(1).replace(",", "")
            try:
                val = float(raw)
            except ValueError:
                continue
            # 'k' suffix pattern
            if pat.groups >= 2 and (m.lastindex or 0) >= 2 and (m.group(2) or "").lower() == "k":
                val *= 1000
            return val, m.span()
    return None, None


def _first_names(name: str) -> List[str]:
    return [t.lower() for t in re.split(r"\s+", name.strip()) if t]


def parse(text: str, members: List[Dict], current_user_id: int) -> Dict:
    """members: [{"id": int, "name": str}]. current_user_id: the person typing."""
    warnings: List[str] = []
    original = text.strip()
    lower = original.lower()

    id_by_name = {}
    for m in members:
        for fn in _first_names(m["name"]):
            id_by_name.setdefault(fn, m["id"])
    member_ids = {m["id"] for m in members}
    name_by_id = {m["id"]: m["name"] for m in members}

    # ---- amount ----
    amount, amount_span = _extract_amount(lower)
    if amount is None:
        warnings.append("Couldn't find an amount — please enter it.")

    # ---- who paid ----
    paid_by = current_user_id
    # "<name> paid" => that member is the payer
    for fn, uid in id_by_name.items():
        if re.search(rf"\b{re.escape(fn)}\b\s+{_PAYER_VERB}", lower):
            paid_by = uid
            break
    else:
        # "i paid" / bare "paid" with no name => current user (already default)
        pass

    # ---- participants (whom to split among) ----
    mentioned = set()
    for fn, uid in id_by_name.items():
        if re.search(rf"\b{re.escape(fn)}\b", lower):
            mentioned.add(uid)
    if any(re.search(rf"\b{re.escape(w)}\b", lower) for w in _SELF_WORDS):
        mentioned.add(current_user_id)

    everyone = any(re.search(rf"\b{re.escape(w)}\b", lower) for w in _EVERYONE_WORDS)
    if everyone:
        participants = set(member_ids)
    elif mentioned:
        participants = set(mentioned)
        participants.add(paid_by)  # payer is part of an equal split by convention
    else:
        participants = set(member_ids)
        warnings.append("No names found — splitting equally across the whole group.")

    participants &= member_ids
    if not participants:
        participants = {current_user_id}

    # ---- split type (NLP path supports equal only) ----
    split_type = "equal"

    # ---- description ----
    description = _extract_description(original, amount_span, id_by_name)
    if not description:
        description = "Shared expense"
        warnings.append("Couldn't pull a description — using a placeholder.")

    # ---- category via ML ----
    category, _conf = categorizer.predict(description)

    return {
        "ok": amount is not None,
        "amount": amount,
        "description": description,
        "category": category,
        "paid_by": paid_by,
        "paid_by_name": name_by_id.get(paid_by),
        "split_type": split_type,
        "participant_ids": sorted(participants),
        "participant_names": [name_by_id[i] for i in sorted(participants) if i in name_by_id],
        "warnings": warnings,
    }


def _extract_description(original: str, amount_span, id_by_name) -> str:
    """Prefer the phrase after 'for'; otherwise reconstruct from leftover words."""
    lower = original.lower()

    # Pattern: "... for <desc> [with|between|among|,] ..."
    m = re.search(r"\bfor\s+(.+?)(?:\s+with\b|\s+between\b|\s+among\b|,|$)", lower)
    if m:
        cand = m.group(1).strip()
        cand = _clean_desc(cand, id_by_name)
        if cand:
            return _titlecase(cand)

    # Fallback: strip amount, names, and stopwords; keep the rest.
    work = original
    if amount_span:
        work = original[:amount_span[0]] + " " + original[amount_span[1]:]
    tokens = re.findall(r"[a-zA-Z']+", work.lower())
    kept = [t for t in tokens if t not in _STOP and t not in id_by_name]
    return _titlecase(" ".join(kept)) if kept else ""


def _clean_desc(text: str, id_by_name) -> str:
    tokens = re.findall(r"[a-zA-Z']+", text.lower())
    kept = [t for t in tokens if t not in _STOP and t not in id_by_name]
    return " ".join(kept)


def _titlecase(s: str) -> str:
    s = s.strip()
    return s[:1].upper() + s[1:] if s else s
