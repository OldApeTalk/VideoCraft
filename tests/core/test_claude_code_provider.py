"""core.ai.providers.claude_code — CLI subprocess failure surfacing.

A non-zero exit with empty stderr used to raise "CLI failed: <no stderr>" with
zero diagnostic content, even when the CLI had written the actual reason to
stdout (--output-format json/text writes there on failure too). Pins the fix:
stdout is now the fallback source for both the reported message and the
kind-sniffing keywords.
"""

from __future__ import annotations

import subprocess

import pytest

from core.ai.errors import AIError, Kind
from core.ai.providers import claude_code


class _FakeProc:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    def communicate(self, input=None, timeout=None):
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode

    def terminate(self):
        pass


@pytest.fixture(autouse=True)
def _no_which(monkeypatch):
    # Skip the shutil.which(.cmd) resolution dance — irrelevant to this test
    # and environment-dependent (whether a real `claude` is on PATH here).
    monkeypatch.setattr(claude_code.shutil, "which", lambda exe: None)


def test_failure_falls_back_to_stdout_when_stderr_empty(monkeypatch):
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: _FakeProc(1, "some diagnostic the CLI printed to stdout", ""),
    )
    with pytest.raises(AIError) as exc_info:
        claude_code._run(["claude", "-p"], {}, "prompt")
    err = exc_info.value
    assert err.kind is Kind.UNKNOWN
    assert "some diagnostic the CLI printed to stdout" in str(err)
    assert "<no stderr>" not in str(err)


def test_failure_prefers_stderr_when_present(monkeypatch):
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: _FakeProc(1, "stdout noise", "the real stderr reason"),
    )
    with pytest.raises(AIError) as exc_info:
        claude_code._run(["claude", "-p"], {}, "prompt")
    assert "the real stderr reason" in str(exc_info.value)


def test_no_output_at_all_reports_no_output(monkeypatch):
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: _FakeProc(1, "", ""),
    )
    with pytest.raises(AIError) as exc_info:
        claude_code._run(["claude", "-p"], {}, "prompt")
    assert "<no output>" in str(exc_info.value)


def test_auth_kind_sniffed_from_stdout_fallback(monkeypatch):
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: _FakeProc(1, "Error: not logged in", ""),
    )
    with pytest.raises(AIError) as exc_info:
        claude_code._run(["claude", "-p"], {}, "prompt")
    assert exc_info.value.kind is Kind.AUTH


def test_oauth_session_expired_classified_as_auth(monkeypatch):
    # Real-world phrasing (observed live): the CLI's actual wording doesn't
    # contain "not authorized"/"not logged in", so it used to fall through
    # to UNKNOWN — misrouting the UI's remediation for an auth failure.
    monkeypatch.setattr(
        subprocess, "Popen",
        lambda *a, **k: _FakeProc(
            1, "Failed to authenticate: OAuth session expired and could not be refreshed", ""
        ),
    )
    with pytest.raises(AIError) as exc_info:
        claude_code._run(["claude", "-p"], {}, "prompt")
    assert exc_info.value.kind is Kind.AUTH
