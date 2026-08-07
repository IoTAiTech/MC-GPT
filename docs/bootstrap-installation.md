<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.3 | Date: 2026-08-07 -->
# Verified Bootstrap Installation

Every bootstrap downloads or accepts one exact ALL-IN-ONE package, verifies the required SHA-256, then invokes the same canonical transactional installer.

```bash
curl -fsSL https://raw.githubusercontent.com/IoTAiTech/MC-GPT/main/installers/bootstrap.sh -o bootstrap.sh
sh bootstrap.sh --sha256 EXPECTED_RELEASE_SHA256 --apply
```

```bash
npx @iot-ai-tech/iot-ai@6.7.0-beta.3 install --sha256 EXPECTED_RELEASE_SHA256 --apply
```

The bootstrap never bypasses package verification, does not patch a live version in place, preserves settings/databases/customer data, and reports rollback and log locations. Real GitHub release download and real Windows on-device qualification remain external gates until their receipts exist.
