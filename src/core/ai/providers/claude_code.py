"""Claude Code subprocess provider (type='claude_code').

Invokes the local `claude -p` CLI headless; no API key — the CLI handles its
own auth via claude.com login. The prompt is piped over stdin to avoid
Windows' ~32KB command-line length ceiling.

--permission-mode bypassPermissions is safe here because we never ask the
model to use Write/Edit; we only consume its text output.

Phase 1: extracted verbatim from ai_router.py. Phase 7 will map subprocess
errors (FileNotFoundError, TimeoutExpired, non-zero exit) to AIError kinds.
"""

import json
import subprocess

from core.ai.providers._json_utils import parse_json_response


def call(cfg: dict, model_id: str, prompt: str) -> str:
    """Plain text completion."""
    cmd = _cmd(cfg, model_id, output_format="text")
    return _run(cmd, cfg, prompt)


def call_json(cfg: dict, model_id: str, prompt: str, schema: dict) -> dict:
    """Structured JSON completion.

    Uses --output-format json, which wraps the model's text in a result
    envelope: {"type":"result","subtype":"success","result":"...","cost_usd":...}.
    The envelope's `result` field is the model's raw text; since we ask the
    model to emit JSON, we parse that string a second time.
    """
    cmd = _cmd(cfg, model_id, output_format="json")
    full_prompt = (
        f"{prompt}\n\n"
        "Respond with ONLY a single JSON object that strictly matches "
        "this JSON Schema:\n"
        f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
        "No prose. No markdown. No code fences. Just the JSON object."
    )
    envelope_raw = _run(cmd, cfg, full_prompt)

    try:
        envelope = json.loads(envelope_raw)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"ClaudeCode CLI returned non-JSON stdout: {envelope_raw[:300]!r}"
        )
    inner_text = envelope.get("result", "")
    if not inner_text:
        raise RuntimeError(
            f"ClaudeCode result envelope missing 'result' field: "
            f"{str(envelope)[:200]!r}"
        )
    return parse_json_response(inner_text, provider_hint="ClaudeCode")


def _cmd(cfg: dict, model_id: str, *, output_format: str) -> list:
    """Build the argv list for a headless `claude -p` invocation."""
    executable = cfg.get("executable") or "claude"
    cmd = [
        executable, "-p",
        "--output-format", output_format,
        "--permission-mode", "bypassPermissions",
    ]
    if model_id:
        cmd += ["--model", model_id]
    extra = cfg.get("extra_args") or []
    if extra:
        cmd += list(extra)
    return cmd


def _run(cmd: list, cfg: dict, prompt: str) -> str:
    """Spawn the Claude CLI subprocess with prompt on stdin, return stdout.
    Raises RuntimeError on missing binary, timeout, or non-zero exit."""
    executable = cmd[0] if cmd else "claude"
    try:
        result = subprocess.run(
            cmd,
            input=prompt,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=int(cfg.get("timeout_sec", 600)),
        )
    except FileNotFoundError:
        raise RuntimeError(
            f"Claude Code CLI not found: {executable!r}. "
            "Install from https://claude.com/claude-code and ensure it "
            "is on PATH, or set a full path in the Router Manager."
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(
            f"Claude Code CLI timed out after {cfg.get('timeout_sec')}s"
        )
    if result.returncode != 0:
        tail = (result.stderr or "").strip().splitlines()[-10:]
        raise RuntimeError("claude code failed: " + " | ".join(tail))
    return (result.stdout or "").strip()
