# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.4 | Date: 2026-08-08
from __future__ import annotations

import sys

from .cli import main, normalize_meeting_argv


def suite_main():
    return main(sys.argv[1:])


def help_main():
    return main(["help", *sys.argv[1:]])


def setup_main():
    return main(["setup", *sys.argv[1:]])


def meeting_main():
    return main(normalize_meeting_argv(sys.argv[1:]))


def provider_main():
    return main(["provider", *sys.argv[1:]])


def settings_main():
    return main(["settings", *sys.argv[1:]])


def tasks_main():
    return main(["tasks", *sys.argv[1:]])


def multicoder_main():
    return main(["multi-coder", *sys.argv[1:]])


def report_main():
    return main(["report", *sys.argv[1:]])


def knowledge_main():
    return main(["knowledge", *sys.argv[1:]])


def privacy_main():
    return main(["privacy", *sys.argv[1:]])


def update_main():
    return main(["update", *sys.argv[1:]])


def status_main():
    return main(["status", *sys.argv[1:]])


def diagnostics_main():
    return main(["diagnostics", *sys.argv[1:]])
