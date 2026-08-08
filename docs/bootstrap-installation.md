<!-- Author: Dr.-Ing. Babak Sorkhpour, with AI assistance | Version: 6.7.0-beta.5 | Date: 2026-08-08 -->
# Verified bootstrap installation

All routes require the exact ALL-IN-ONE SHA-256 and invoke the same clean transactional installer. Omit `--apply` for a non-mutating plan.

```bash
curl -fsSL https://raw.githubusercontent.com/IoTAiTech/MC-GPT/main/installers/bootstrap.sh -o bootstrap.sh
sh bootstrap.sh --sha256 EXPECTED_SHA256 --apply
```

```bash
npx --yes @iot-ai-tech/iot-ai@6.7.0-beta.5 install --sha256 EXPECTED_SHA256 --apply
```

```bash
npm exec --yes --package=@iot-ai-tech/iot-ai@6.7.0-beta.5 -- iot-ai-bootstrap install --sha256 EXPECTED_SHA256 --apply
```

The bootstrap rejects tampered bytes, unsafe archives and missing manifests. It preserves settings, databases, customer data and rollback state. A local HTTP server qualification is not a substitute for a live GitHub Release download and hosted attestation.
