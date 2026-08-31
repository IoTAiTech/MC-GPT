<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 1.0.0 | Date: 2026-08-28 -->

# Demo task: deterministic login rate limiting

## Outcome

Add a small, testable rate limiter to the disposable authentication fixture.

## Acceptance criteria

1. Preserve the existing `authenticate(username, password) -> bool` behaviour for callers that are not rate-limited.
2. Add a public rate-limiter abstraction with an injected clock; tests must not sleep or depend on wall-clock timing.
3. After three failed attempts for one username inside a 60-second window, further attempts for that username are blocked until the window expires.
4. A successful login clears the failure state for that username.
5. One user's failures do not block another user.
6. Invalid and unknown usernames must not reveal whether the account exists.
7. Add deterministic unit tests for the threshold, expiry, reset and user isolation.
8. Run all tests against the post-change tree.
9. Return changed-file hashes, the exact test command and a brief security review.

## Non-goals

- no HTTP framework;
- no database;
- no network calls;
- no background service;
- no production claim;
- no customer data.

## Required workflow

```text
inspect baseline
→ freeze acceptance criteria
→ one authorised writer
→ independent security/reliability review
→ post-change tests
→ bounded repair if a test fails
→ final evidence table
```
