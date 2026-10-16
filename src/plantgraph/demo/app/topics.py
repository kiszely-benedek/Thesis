"""Topic of a question family, so the example list needs no family code.

A family is one kind of question the generator asks ("is A connected to B", "which valves
isolate X"). The visitor sees only the topic heading the family belongs to. The table lives
in `static/labels.en.json` (`family_topics`, `topics`); this module is its typed reader.
"""

from __future__ import annotations

from plantgraph.demo.app.labels import load_labels
from plantgraph.qa.models import QuestionFamily

#: Topic codes in the order the page lists them (the order of `topics` in the JSON).
TOPIC_ORDER: tuple[str, ...] = tuple(load_labels().topics)


def topic_of(family: QuestionFamily) -> str:
    """The topic code of a family; the page turns it into a heading with `labels.topics`.

    Raises:
        KeyError: the family has no topic yet (a new family was added without one).
    """
    topic = load_labels().family_topics.get(family.value)
    if topic is None:
        raise KeyError(f"expected a topic for family {family.value}, found none in labels.en.json")
    return topic
