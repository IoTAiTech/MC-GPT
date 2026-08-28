"""Minimal disposable authentication fixture for the MC-GPT quickstart.

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.0.0
"""

from __future__ import annotations

from hmac import compare_digest

_USERS: dict[str, str] = {
    "demo": "correct-horse-battery-staple",
    "reviewer": "read-only-example",
}


def authenticate(username: str, password: str) -> bool:
    """Return True only for an exact username/password match.

    The fixture intentionally has no rate limiting. TASK.md asks the coding
    agents to add it without changing the existing successful-login contract.
    """

    expected = _USERS.get(username)
    return expected is not None and compare_digest(expected, password)
