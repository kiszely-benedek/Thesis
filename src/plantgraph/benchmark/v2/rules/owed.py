"""The rules a plant is known to break today, and the task that will fix each one (design 17.7).

Generation raises on any violation of a rule that is NOT listed here. A listed rule is still
checked and still reported (`RuleRow.owed_by` names the task), but it does not stop the build.
T7 closed the last entry (PLT-STREAM-CLOSURE): the dict is empty, as gate G0c requires before any
corpus of the final experiment is built, so `verify_generated` raises on every violation.
"""

from __future__ import annotations

#: rule id -> the task that owes its fix
OWED_FIXES: dict[str, str] = {}
