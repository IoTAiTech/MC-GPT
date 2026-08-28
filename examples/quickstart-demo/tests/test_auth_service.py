"""Baseline tests for the disposable MC-GPT quickstart fixture.

Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
Version: 1.0.0
"""

from __future__ import annotations

import unittest

from auth_service import authenticate


class AuthenticationBaselineTests(unittest.TestCase):
    def test_valid_credentials_are_accepted(self) -> None:
        self.assertTrue(authenticate("demo", "correct-horse-battery-staple"))

    def test_wrong_password_is_rejected(self) -> None:
        self.assertFalse(authenticate("demo", "wrong"))

    def test_unknown_user_is_rejected(self) -> None:
        self.assertFalse(authenticate("unknown", "anything"))


if __name__ == "__main__":
    unittest.main()
