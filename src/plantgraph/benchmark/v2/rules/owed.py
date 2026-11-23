"""The rules a plant is known to break today, and the task that will fix each one (design 17.7).

Generation raises on any violation of a rule that is NOT listed here. A listed rule is still
checked and still reported (`RuleRow.owed_by` names the task), but it does not stop the build.
Each later task deletes the entries it closes; gate G0c requires the dict to be empty before any
corpus of the final experiment is built.
"""

from __future__ import annotations

#: rule id -> the task that owes its fix
OWED_FIXES: dict[str, str] = {
    # T7a closed the plant-boundary ends; what is left (58 over seeds 1-5) is relief outlets and
    # fuel-gas bleeds, which T7 closes (design 17.4)
    "PLT-STREAM-CLOSURE": "T7",
}
