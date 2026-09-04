# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.8.0-beta.1 | Date: 2026-09-05
"""Optional local static-preview runner. No provider calls or remote resources.

Requires an operator-provisioned Playwright and Chromium installation. This is
an automated DOM/layout check, not a full WCAG audit or aesthetic approval.
"""
from __future__ import annotations

import hashlib
import json
import mimetypes
import os
from pathlib import Path
import shutil
import sys
from urllib.parse import unquote, urlsplit


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read(root: Path, relative: str) -> bytes:
    path = root / relative
    if path.is_absolute() and not path.is_relative_to(root):
        raise ValueError("source-containment")
    if ".." in Path(relative).parts or Path(relative).is_absolute():
        raise ValueError("source-containment")
    current = root
    for part in Path(relative).parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("source-symlink")
    if not path.is_file() or path.stat().st_size > 12_000_000:
        raise ValueError("source-size-or-type")
    return path.read_bytes()


DOM_CHECKS = """() => {
  const controls = [...document.querySelectorAll('button,a[href],input,select,textarea')];
  const named = e => !!((e.getAttribute('aria-label') || e.innerText || e.getAttribute('title') || '').trim()
    || (e.labels && e.labels.length) || e.getAttribute('aria-labelledby'));
  const ids = [...document.querySelectorAll('[id]')].map(e => e.id);
  const visible = controls.filter(e => {const r = e.getBoundingClientRect(); return r.width && r.height;});
  return {
    horizontal_overflow: document.documentElement.scrollWidth > innerWidth + 1,
    clipping: visible.some(e => {const r=e.getBoundingClientRect();return r.left < -1 || r.right > innerWidth + 1;}),
    accessibility: {
      document_language: !!document.documentElement.lang,
      document_title: !!document.title.trim(),
      main_landmark: document.querySelectorAll('main,[role=main]').length === 1,
      primary_heading: document.querySelectorAll('h1').length === 1,
      image_alternatives: [...document.images].every(e => e.hasAttribute('alt')),
      images_loaded: [...document.images].every(e => e.complete && e.naturalWidth > 0),
      named_controls: controls.every(named),
      unique_ids: new Set(ids).size === ids.length
    }
  };
}"""


def main() -> int:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print(json.dumps({"available": False, "reason": "playwright-not-installed"}))
        return 78
    binary = os.environ.get("IOT_AI_CHROMIUM") or shutil.which("chromium") or shutil.which("google-chrome")
    probe = "--probe" in sys.argv[1:]
    try:
        with sync_playwright() as playwright:
            options = {"headless": True, "chromium_sandbox": os.environ.get("IOT_AI_VISUAL_ISOLATED_CONTAINER") != "1"}
            if binary:
                options["executable_path"] = binary
            browser = playwright.chromium.launch(**options)
            try:
                if probe:
                    page = browser.new_page()
                    page.set_content("<!doctype html><title>Probe</title>")
                    available = page.title() == "Probe"
                    print(json.dumps({"schema": "iot-ai.visual-runner-probe.v1", "available": available, "version": browser.version}))
                    return 0 if available else 78
                raw = sys.stdin.buffer.read(262145)
                if len(raw) > 262144:
                    raise ValueError("request-size")
                request = json.loads(raw)
                source, output = Path(request["source_root"]), Path(request["artifact_root"])
                assets = request["assets"]
                payloads = {key: _read(source, key) for key in assets}
                actual = {key: _sha(data) for key, data in payloads.items()}
                if actual != assets:
                    raise ValueError("source-drift")
                source_digest = _sha(json.dumps(actual, sort_keys=True, separators=(",", ":"), allow_nan=False).encode())
                if source_digest != request["source_digest"] or output.is_symlink():
                    raise ValueError("source-or-output-invalid")
                blocked_requests, page_errors = [], []
                viewports, a11y, states = {}, {}, {}
                for name, (width, height) in request["viewports"].items():
                    if name not in {"desktop", "tablet", "mobile"}:
                        raise ValueError("viewport-name")
                    context = browser.new_context(viewport={"width": width, "height": height},
                        device_scale_factor=1, service_workers="block", accept_downloads=False, offline=True)
                    try:
                        def route_handler(route):
                            url = urlsplit(route.request.url)
                            key = unquote(url.path).lstrip("/")
                            if url.scheme == "http" and url.hostname == "render.invalid" and key in payloads:
                                mime = mimetypes.guess_type(key)[0] or "application/octet-stream"
                                route.fulfill(status=200, content_type=mime, body=payloads[key])
                            else:
                                blocked_requests.append(1)
                                route.abort()
                        context.route("**/*", route_handler)
                        # WebSockets bypass ordinary HTTP route handlers.
                        def block_socket(websocket):
                            blocked_requests.append(1)
                            websocket.close()
                        context.route_web_socket("**/*", block_socket)
                        page = context.new_page()
                        page.on("pageerror", lambda error: page_errors.append(1))
                        # Render the verified bytes directly. No file URL, navigation, or
                        # local-server exemption is needed for this static preview.
                        page.set_content(payloads[request["entry"]].decode("utf-8"), wait_until="load", timeout=10000)
                        checks = page.evaluate(DOM_CHECKS)
                        screenshot = page.screenshot(type="png", full_page=False, animations="disabled")
                        path = output / f"{name}.png"
                        with path.open("xb") as stream:
                            stream.write(screenshot)
                        viewports[name] = {"width": width, "height": height,
                            "screenshot_sha256": _sha(screenshot),
                            "horizontal_overflow": checks["horizontal_overflow"], "clipping": checks["clipping"]}
                        a11y[name] = checks["accessibility"]
                        states[name] = {}
                        for state in ("loading", "empty", "error"):
                            trigger = page.locator(f'[data-qa-state="{state}"]')
                            panel = page.locator(f'[data-qa-panel="{state}"]')
                            ok = False
                            if trigger.count() == 1 and panel.count() == 1:
                                trigger.click(timeout=1500)
                                ok = panel.is_visible()
                            states[name][state] = ok
                    finally:
                        context.close()
                after = {key: _sha(_read(source, key)) for key in assets}
                if after != assets:
                    raise ValueError("source-drift")
                checks = {
                    "automated_accessibility": {"executed": True, "passed": all(all(v.values()) for v in a11y.values()), "scope": "dom-structure-v1", "results": a11y},
                    "interaction_states": {"executed": True, "passed": all(all(v.values()) for v in states.values()), "results": states},
                    "network_isolation": {"executed": True, "passed": not blocked_requests, "blocked_request_count": len(blocked_requests), "scope": "offline-browser-resource-routing", "os_network_namespace_proven": False},
                    "page_errors_absent": {"executed": True, "passed": not page_errors, "count": len(page_errors)},
                }
                passed = all(v["passed"] for v in checks.values()) and all(not v["horizontal_overflow"] and not v["clipping"] for v in viewports.values())
                receipt = {"schema": "iot-ai.visual-runner-result.v1", "decision": "pass" if passed else "block",
                    "run_id": request["run_id"], "source_digest": source_digest,
                    "runner_digest": request["runner_digest"], "browser_version": browser.version,
                    "viewports": viewports, "checks": checks,
                    "render_mode": "verified-bytes-set-content",
                    "full_accessibility_certification": False, "human_design_review_required": True}
                with (output / "receipt.json").open("x", encoding="utf-8") as stream:
                    json.dump(receipt, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
                print(json.dumps({"decision": receipt["decision"], "provider_calls": 0}))
                return 0 if passed else 1
            finally:
                browser.close()
    except Exception:
        # Deliberately suppress raw browser errors: they can expose local paths.
        print(json.dumps({"available": False, "decision": "block", "reason": "visual-runner-failed"}))
        return 78 if probe else 2


if __name__ == "__main__":
    raise SystemExit(main())
