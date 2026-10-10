"""Which host OpenRouter says served a completion."""

from __future__ import annotations


def served_by(completion: object) -> str | None:
    """The host named in the completion body's top-level `provider` field, if any.

    OpenRouter adds this field to the standard OpenAI shape; the SDK keeps unknown
    fields as plain attributes, so it is read with `getattr`.
    """
    provider = getattr(completion, "provider", None)
    return provider if isinstance(provider, str) and provider else None
