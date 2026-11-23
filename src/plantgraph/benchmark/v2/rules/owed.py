"""The rules a plant is known to break today, and the task that will fix each one (design 17.7).

Generation raises on any violation of a rule that is NOT listed here. A listed rule is still
checked and still reported (`RuleRow.owed_by` names the task), but it does not stop the build.
Each later task deletes the entries it closes; gate G0c requires the dict to be empty before any
corpus of the final experiment is built.
"""

from __future__ import annotations

#: rule id -> the task that owes its fix
OWED_FIXES: dict[str, str] = {
    # 71 plant-boundary ends belong to T7a and 58 relief outlets and bleeds to T7; T7a is a
    # separate task, so the whole rule is owed to T7 until both have landed (design 17.4)
    "PLT-STREAM-CLOSURE": "T7",
}
