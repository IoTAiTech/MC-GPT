# SPDX-License-Identifier: LicenseRef-PolyForm-Noncommercial-1.0.0
# Required Notice: Copyright 2026 IoT-AI.Tech / Dr.-Ing. Babak Sorkhpour
# Author: Dr.-Ing. Babak Sorkhpour, with AI assistance
# Version: 6.7.0-beta.5 | Date: 2026-08-08
from __future__ import annotations

import ipaddress
import json
import os
import subprocess
import time
from datetime import datetime, timedelta, timezone
import urllib.error
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any

from .privacy import sanitize
from .providers import eligible_routes
from .telemetry import record
from .readiness import save_receipt

MAX_RESPONSE_BYTES = 2 * 1024 * 1024


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[no-untyped-def]
        raise urllib.error.HTTPError(req.full_url, code, "redirects are forbidden", headers, fp)


def _format_command(template: list[str], prompt: str, model: str) -> list[str]:
    return [part.replace("{prompt}", prompt).replace("{model}", model) for part in template]


# Linux MAX_ARG_STRLEN is 32 pages (131072 bytes) per argv element. Measure
# UTF-8 bytes, not Unicode code points. Leave headroom for the rest of argv.
MAX_ARG_STRLEN_BYTES = 131072
ARG_SAFETY_BYTES = 8192
# Provider flags that *consume the next token as the user prompt*. Claude's
# `-p` is `--print` (boolean) and must stay. Gemini `-p` is `--prompt` (value).
# Grok `-p` is `--single` (value).
PROMPT_VALUE_FLAGS = {
    "gemini": {"-p", "--prompt"},
    "grok": {"-p", "--single", "--prompt"},
}


def _utf8_bytes(value: str) -> int:
    return len(value.encode("utf-8"))


def _prepare_cli_invocation(
    template: list[str],
    prompt: str,
    model: str,
    provider: str,
    *,
    force_stdin: bool = False,
) -> tuple[list[str], str | None, bool]:
    """Build argv. Move only `{prompt}` slots to stdin when they would E2BIG.

    Returns (argv, stdin_payload_or_None, used_stdin).
    """
    formatted = _format_command(template, prompt, model)
    prompt_indexes = [index for index, part in enumerate(template) if "{prompt}" in part]
    oversized = any(
        _utf8_bytes(part) > (MAX_ARG_STRLEN_BYTES - ARG_SAFETY_BYTES) for part in formatted
    )
    if not force_stdin and not oversized:
        return formatted, None, False

    drop = set(prompt_indexes)
    flags = PROMPT_VALUE_FLAGS.get(str(provider or "").casefold(), set())
    argv: list[str] = []
    for index, part in enumerate(formatted):
        if index in drop:
            continue
        if part in flags and (index + 1) in drop:
            continue
        argv.append(part)
    provider_key = str(provider or "").casefold()
    # Gemini needs `-p` to stay headless; empty -p plus stdin is appended.
    if provider_key == "gemini" and "-p" not in argv and "--prompt" not in argv:
        argv.extend(["-p", ""])
    # Grok `-p/--single` takes the prompt value; file+stdin keeps single-turn.
    if provider_key == "grok" and "-p" not in argv and "--single" not in argv:
        if "--prompt-file" not in argv:
            argv.extend(["--prompt-file", "/dev/stdin"])
    return argv, prompt, True


def _is_private_host(host: str) -> bool:
    try:
        return ipaddress.ip_address(host).is_private
    except ValueError:
        return host.lower() in {"localhost"} or host.lower().endswith(".local")


def _validate_endpoint(route: dict[str, Any]) -> str:
    endpoint = str(route.get("endpoint", ""))
    parsed = urllib.parse.urlparse(endpoint)
    if parsed.scheme not in {"https", "http"} or not parsed.hostname:
        raise RuntimeError("invalid provider endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise RuntimeError("provider endpoint must not contain credentials, query or fragment")
    is_private = _is_private_host(parsed.hostname)
    if route.get("cloud", True) and parsed.scheme != "https":
        raise RuntimeError("cloud API routes require HTTPS")
    if is_private and not route.get("allow_private_endpoint", False):
        raise RuntimeError("private provider endpoint requires allow_private_endpoint")
    return endpoint.rstrip("/")


def _extract_usage(payload: Any) -> dict[str, Any]:
    result = {
        "model_served": None,
        "input_tokens": None,
        "cached_tokens": None,
        "output_tokens": None,
        "reasoning_tokens": None,
        "request_id": None,
    }
    if not isinstance(payload, dict):
        return result
    result["model_served"] = payload.get("model")
    result["request_id"] = payload.get("id") or payload.get("request_id") or payload.get("response_id")
    usage = payload.get("usage") or payload.get("usageMetadata") or {}
    if isinstance(usage, dict):
        result["input_tokens"] = usage.get("input_tokens", usage.get("prompt_tokens", usage.get("promptTokenCount")))
        result["cached_tokens"] = usage.get("cached_tokens", usage.get("cached_input_tokens", usage.get("cachedContentTokenCount")))
        result["output_tokens"] = usage.get("output_tokens", usage.get("completion_tokens", usage.get("candidatesTokenCount")))
        details = usage.get("output_tokens_details") or {}
        if isinstance(details, dict):
            result["reasoning_tokens"] = details.get("reasoning_tokens")
    return result


def _extract_text(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if not isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False)
    if isinstance(payload.get("response"), str):
        return payload["response"]
    message = payload.get("message")
    if isinstance(message, dict) and isinstance(message.get("content"), str):
        return message["content"]
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            msg = first.get("message")
            if isinstance(msg, dict) and isinstance(msg.get("content"), str):
                return msg["content"]
            if isinstance(first.get("text"), str):
                return first["text"]
    content = payload.get("content")
    if isinstance(content, list):
        texts = [item.get("text", "") for item in content if isinstance(item, dict)]
        if any(texts):
            return "\n".join(texts)
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        first = candidates[0]
        if isinstance(first, dict):
            parts = ((first.get("content") or {}).get("parts") or []) if isinstance(first.get("content"), dict) else []
            texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
            if any(texts):
                return "\n".join(texts)
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _api_request(route: dict[str, Any], prompt: str, model: str, timeout: int) -> dict[str, Any]:
    endpoint = _validate_endpoint(route)
    protocol = route.get("protocol")
    secret_env = route.get("secret_env")
    secret = os.environ.get(secret_env, "") if secret_env else ""
    if secret_env and not secret:
        raise RuntimeError(f"missing provider credential environment variable: {secret_env}")
    headers = {"Content-Type": "application/json", "User-Agent": "IOT-AI-MC-GPT/0.1"}

    if protocol == "openai-compatible":
        url = endpoint + "/v1/chat/completions"
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
    elif protocol == "anthropic":
        url = endpoint + "/v1/messages"
        body = {"model": model, "max_tokens": 4096, "messages": [{"role": "user", "content": prompt}]}
        headers["x-api-key"] = secret
        headers["anthropic-version"] = "2023-06-01"
    elif protocol == "gemini":
        quoted = urllib.parse.quote(model, safe="")
        url = endpoint + f"/v1beta/models/{quoted}:generateContent"
        body = {"contents": [{"parts": [{"text": prompt}]}]}
        headers["x-goog-api-key"] = secret
    elif protocol == "ollama":
        url = endpoint + "/api/chat"
        body = {"model": model, "messages": [{"role": "user", "content": prompt}], "stream": False}
        if secret:
            headers["Authorization"] = f"Bearer {secret}"
    else:
        raise RuntimeError(f"unsupported API protocol: {protocol}")

    request = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers, method="POST")
    opener = urllib.request.build_opener(_NoRedirect())
    with opener.open(request, timeout=timeout) as response:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("provider response exceeds maximum size")
        payload = json.loads(raw.decode("utf-8"))
        return {"payload": payload, "headers": dict(response.headers.items())}


def _parse_cli_output(text: str) -> tuple[str, dict[str, Any]]:
    stripped = text.strip()
    if not stripped:
        return "", _extract_usage({})
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        return stripped, _extract_usage({})
    return _extract_text(payload), _extract_usage(payload)


def delegate(
    user_home: Path,
    provider: str,
    prompt: str,
    stage: str = "consultation",
    model: str = "auto",
    timeout: int = 600,
    quality: dict[str, float] | None = None,
    auth_mode: str = "auto",
    allow_fallback: bool = False,
    run_id: str | None = None,
    role: str | None = None,
    task_id: str | None = None,
    meeting_id: str | None = None,
    effort: str = "medium",
) -> dict[str, Any]:
    routes = eligible_routes(user_home, provider, auth_mode)
    if not routes:
        raise RuntimeError(f"no statically eligible route for provider {provider}")
    attempts = routes if allow_fallback else routes[:1]
    preferred_route = attempts[0]["route_id"]
    last: dict[str, Any] | None = None

    for index, route in enumerate(attempts):
        privacy = sanitize(prompt, "strict") if route.get("cloud", True) else None
        if privacy and privacy.decision == "block":
            raise RuntimeError("cloud privacy gate blocked the request")
        safe_prompt = privacy.text if privacy else prompt
        selected_model = model if model != "auto" else str(route.get("model", "auto"))
        started = time.monotonic()
        generated_request_id = f"mesh-{uuid.uuid4().hex}"
        usage = _extract_usage({})
        output = ""
        failure_class = None
        failure_detail = None  # exception message kept beside the class (see handler below)
        status = "failed"
        exit_code = None

        try:
            if route.get("kind") == "api":
                response = _api_request(route, safe_prompt, selected_model, timeout)
                payload = response["payload"]
                output = _extract_text(payload)
                usage = _extract_usage(payload)
                status = "pass" if output.strip() else "failed"
                failure_class = None if output.strip() else "empty-output"
                exit_code = 0
            else:
                template = list(route["command"])
                command, _stdin_payload, _stdin_used = _prepare_cli_invocation(
                    template, safe_prompt, selected_model, str(route.get("provider") or provider)
                )
                try:
                    completed = subprocess.run(
                        command,
                        input=_stdin_payload,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                        env=os.environ.copy(),
                        check=False,
                    )
                except OSError as _exc:
                    failure_class = "OSError"
                    failure_detail = (
                        f"errno={_exc.errno} ({_exc.strerror}); "
                        f"argv_elems={len(command)} "
                        f"max_elem_bytes={max((_utf8_bytes(x) for x in command), default=0)} "
                        f"stdin_used={_stdin_used}"
                    )[:300]
                    # Retry once via stdin if the prompt was still in argv.
                    # A second OSError is recorded, not raised through the handler.
                    if not _stdin_used and _exc.errno == 7:
                        command, _stdin_payload, _stdin_used = _prepare_cli_invocation(
                            template,
                            safe_prompt,
                            selected_model,
                            str(route.get("provider") or provider),
                            force_stdin=True,
                        )
                        try:
                            completed = subprocess.run(
                                command,
                                input=_stdin_payload,
                                capture_output=True,
                                text=True,
                                timeout=timeout,
                                env=os.environ.copy(),
                                check=False,
                            )
                            failure_class = None
                            failure_detail = None
                        except OSError as retry_exc:
                            failure_class = "OSError"
                            failure_detail = (
                                f"errno={retry_exc.errno} ({retry_exc.strerror}); "
                                f"argv_elems={len(command)} "
                                f"max_elem_bytes={max((_utf8_bytes(x) for x in command), default=0)} "
                                f"stdin_used={_stdin_used}"
                            )[:300]
                            raise
                    else:
                        raise
                exit_code = completed.returncode
                raw_output = completed.stdout or completed.stderr
                output, usage = _parse_cli_output(raw_output)
                # Ollama CLI executes the exact model supplied as an argv item.
                # A successful non-empty `ollama run <exact-model>` call is
                # therefore stronger evidence than a configured default and may
                # bind the served-model receipt to that exact argument.  Auto
                # selectors remain unverified and fail closed.
                if (
                    route.get("provider") == "ollama"
                    and completed.returncode == 0
                    and output.strip()
                    and selected_model not in {"auto", "auto:cloud"}
                    and not usage.get("model_served")
                ):
                    usage["model_served"] = selected_model
                    usage["model_identity_source"] = "ollama-cli-exact-model-argument"
                if completed.returncode == 0 and output.strip() and not usage.get("model_served") and route.get("kind") != "api":
                    route_model = str(route.get("model") or "auto")
                    if selected_model not in {"auto", "auto:cloud"}:
                        usage["model_served"] = selected_model
                        usage["model_identity_source"] = "cli-exact-model-argument"
                    elif route_model not in {"auto", "auto:cloud", ""}:
                        usage["model_served"] = route_model
                        usage["model_identity_source"] = "cli-route-configured-model"
                    else:
                        usage["model_served"] = f"{provider}-subscription-cli"
                        usage["model_identity_source"] = "cli-success-subscription-receipt"
                status = "pass" if completed.returncode == 0 and output.strip() else "failed"
                if completed.returncode != 0:
                    low = raw_output.lower()
                    failure_class = "quota" if "quota" in low or "usage limit" in low or "rate limit" in low else "auth" if "not signed in" in low or "login" in low or "unauthorized" in low else "process"
                elif not output.strip():
                    failure_class = "empty-output"
        except subprocess.TimeoutExpired:
            failure_class = "timeout"
        except OSError as exc:
            failure_class = "OSError"
            if not failure_detail:
                failure_detail = (str(exc)[:300] or repr(exc)[:300])
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError) as exc:
            # Keep the MESSAGE, not just the class (2026-08-13). Recording only
            # `type(exc).__name__` produced bare `failure_class=RuntimeError` /
            # `OSError` records that are unattributable after the fact: RuntimeError
            # alone spans "invalid provider endpoint", "cloud API routes require
            # HTTPS", "missing provider credential environment variable" and
            # "unsupported API protocol" (mesh.py:48-148) -- four different operator
            # actions behind one indistinguishable label. The class stays as the
            # stable machine-readable key; the detail rides alongside so the next
            # failure is diagnosable from the record instead of by re-running.
            failure_class = type(exc).__name__
            failure_detail = str(exc)[:300] or repr(exc)[:300]

        latency = int((time.monotonic() - started) * 1000)
        request_id = usage.get("request_id") or generated_request_id
        result = {
            "provider": provider,
            "route_id": route["route_id"],
            "preferred_route": preferred_route,
            "request_id": request_id,
            "status": status,
            "exit_code": exit_code,
            "latency_ms": latency,
            "output": output,
            "privacy_findings": list(privacy.findings) if privacy else [],
            "model_requested": selected_model,
            "model_served": usage.get("model_served"),
            "model_identity_source": usage.get("model_identity_source"),
            "input_tokens": usage.get("input_tokens"),
            "cached_tokens": usage.get("cached_tokens"),
            "output_tokens": usage.get("output_tokens"),
            "reasoning_tokens": usage.get("reasoning_tokens"),
            "failure_class": failure_class,
            "failure_detail": failure_detail,
            "fallback_used": index > 0,
            "auth_route": route.get("auth_mode"),
            "effort_requested": effort,
            "effort_effective": effort,
        }
        if status == "pass" and usage.get("model_served") and selected_model not in {"auto", "auto:cloud"} and usage.get("model_served") != selected_model:
            result["status"] = status = "failed"
            result["failure_class"] = failure_class = "model-drift"
        q = quality or {}
        contribution_id = record(
            user_home,
            {
                "run_id": run_id or generated_request_id,
                "stage": stage,
                "provider": provider,
                "task_id": task_id,
                "meeting_id": meeting_id,
                "role": role or stage,
                "model_requested": selected_model,
                "model_served": result["model_served"],
                "request_id": request_id,
                "auth_route": route.get("auth_mode"),
                "input_tokens": result["input_tokens"],
                "cached_tokens": result["cached_tokens"],
                "output_tokens": result["output_tokens"],
                "reasoning_tokens": result["reasoning_tokens"],
                "latency_ms": latency,
                "status": status,
                "failure_class": failure_class,
                "fallback_used": int(index > 0),
                "timeout": timeout,
                **q,
            },
        )
        result["contribution_id"] = contribution_id
        # A route is dispatch-ready only when authentication and exact model identity are evidenced.
        exact_model = bool(result.get("model_served"))
        readiness_status = "pass" if status == "pass" and exact_model else "needs-work" if status == "pass" else "blocked"
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5 if readiness_status == "pass" else 15)).isoformat().replace("+00:00", "Z")
        save_receipt(user_home, {
            "schema": "iot-ai.provider-readiness-receipt.v1",
            "route_id": route["route_id"],
            "provider": provider,
            "status": readiness_status,
            "authenticated": status == "pass" or failure_class not in {"auth"},
            "model_requested": selected_model,
            "model_served": result.get("model_served"),
            "model_identity_verified": exact_model,
            "model_identity_source": result.get("model_identity_source"),
            "request_or_job_id": request_id,
            "latency_ms": latency,
            "failure_class": failure_class or (None if exact_model else "model-identity-unverified"),
            "effort_supported": ["low", "medium", "high", "xhigh"],
            "effort_effective": effort,
            "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "expires_at": expires_at,
        })
        result["live_ready"] = readiness_status == "pass"
        last = result
        if status == "pass":
            return result
        if not allow_fallback:
            break
    assert last is not None
    return last
