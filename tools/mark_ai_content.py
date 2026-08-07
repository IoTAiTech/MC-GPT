# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.3 | Date: 2026-08-07
"""Mark a generated content file with IOT-AI Article 50 provenance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from iot_ai.transparency import mark_file, verify_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("file")
    parser.add_argument("--provider", action="append", default=[])
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--human-reviewed", action="store_true")
    parser.add_argument("--editor")
    parser.add_argument("--public-interest", action="store_true")
    parser.add_argument("--deepfake", action="store_true")
    parser.add_argument("--visible-label", action="store_true")
    parser.add_argument("--verify", action="store_true")
    args = parser.parse_args()
    path = Path(args.file)
    result = verify_file(path) if args.verify else mark_file(
        path,
        model_providers=args.provider,
        model_ids=args.model,
        human_reviewed=args.human_reviewed,
        editorially_responsible_party=args.editor,
        public_interest=args.public_interest,
        deepfake=args.deepfake,
        visible_label_present=args.visible_label,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("decision") == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
