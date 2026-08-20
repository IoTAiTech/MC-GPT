# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-08-20
"""GitHub Packages (GHCR + npm) must publish on every version tag/release."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class GitHubPackagesPublishTests(unittest.TestCase):
    def test_dockerfile_links_image_to_this_repository(self) -> None:
        text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        self.assertIn(
            'org.opencontainers.image.source="https://github.com/IoTAiTech/MC-GPT"',
            text,
        )
        self.assertIn("USER 10001", text)
        self.assertIn("ENTRYPOINT", text)
        self.assertNotIn("GITHUB_TOKEN", text)
        self.assertNotIn("XAI_API_KEY", text)

    def test_release_workflow_publishes_packages_every_version(self) -> None:
        text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
        self.assertIn("packages: write", text)
        self.assertIn("ghcr.io/iotaitech/mc-gpt", text)
        self.assertIn("org.opencontainers.image.source", text)
        self.assertIn("npm.pkg.github.com", text)
        self.assertIn("@iotaitech/mc-gpt", text)
        self.assertIn("types: [published]", text)
        self.assertIn("docker/login-action@", text)
        self.assertIn("docker/build-push-action@", text)
        self.assertIn("linux/amd64,linux/arm64", text)
        self.assertNotIn("--clobber", text)
        self.assertIn("RAW_TAG: ${{ inputs.tag }}", text)
        self.assertIn("TAG=\"${RAW_TAG}\"", text)
        self.assertNotIn("TAG=\"${{ inputs.tag }}\"", text)
        self.assertIn("leaving assets immutable", text)
        self.assertNotIn("refusing to replace assets", text)

    def test_docs_and_contract_require_dockerfile(self) -> None:
        required = (ROOT / "tools" / "verify_repository.py").read_text(encoding="utf-8")
        boundary = (ROOT / "tools" / "public_boundary_check.py").read_text(encoding="utf-8")
        docs = (ROOT / "docs" / "github-packages.md").read_text(encoding="utf-8")
        self.assertIn('"Dockerfile"', required)
        self.assertIn('"docs/github-packages.md"', required)
        self.assertIn('"Dockerfile"', boundary)
        self.assertIn("ghcr.io/iotaitech/mc-gpt", docs)
        self.assertIn("Packages tab", docs)
        self.assertTrue((ROOT / ".dockerignore").is_file())
