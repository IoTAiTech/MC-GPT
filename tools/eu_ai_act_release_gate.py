# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.6.0-beta.3 | Date: 2026-08-06
"""Run the evidence-bound EU AI Act developer-preview release gate."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from iot_ai.eu_ai_act import release_gate


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--profile", choices=("developer-preview", "production"), default="developer-preview")
    args = parser.parse_args()
    result = release_gate(Path(args.root), profile=args.profile)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["decision"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
