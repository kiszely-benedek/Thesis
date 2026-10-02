"""Retrieval strategies: each turns a question's text into a context string (`qa-system.md` §7).

`base.py` holds the `Strategy` protocol and the one function that runs any
strategy through the shared final-answer step; each other module is one
strategy. They differ only in how they pick the context.
"""

from __future__ import annotations
