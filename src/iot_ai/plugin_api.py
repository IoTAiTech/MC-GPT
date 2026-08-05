# SPDX-License-Identifier: LicenseRef-PolyForm-Strict-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.5.0-beta.2 | Date: 2026-08-05

from __future__ import annotations
from typing import Protocol, Any

class WorkSource(Protocol):
    def list_open(self) -> list[dict[str, Any]]: ...
class IdentityBridge(Protocol):
    def current_subject(self) -> str: ...
class AssignmentStore(Protocol):
    def submit(self, assignment: dict[str, Any]) -> str: ...
class ProgressSink(Protocol):
    def publish(self, event: dict[str, Any]) -> None: ...
class EvidenceSink(Protocol):
    def publish(self, evidence: dict[str, Any]) -> str: ...
class DecisionSink(Protocol):
    def submit_for_review(self, result: dict[str, Any]) -> str: ...
