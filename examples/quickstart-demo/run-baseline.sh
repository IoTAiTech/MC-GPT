#!/bin/sh
# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 1.0.0 | Date: 2026-08-28
set -eu
cd "$(dirname "$0")"
PYTHONPATH=. python3 -m unittest discover -s tests -v
