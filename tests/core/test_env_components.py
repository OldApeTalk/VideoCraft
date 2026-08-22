"""core.env.install_one — restart-required signal.

Overwriting py-extra's files on disk never touches a module the running
process already `import`-ed: Python serves the cached sys.modules entry
regardless of what's on disk until the process restarts. install_one() must
report this so the UI can tell the user a restart is needed instead of
letting them believe the click alone fixed it (the exact confusion this
pins: user tries yt-dlp update in-app, it appears to succeed, downloads
still fail with the old bug — only a full app restart actually helped).
"""

from __future__ import annotations

import sys

import pytest

from core.env import components as env_components
from core.env.types import EnvComponent, DetectResult


@pytest.fixture
def fake_component(monkeypatch):
    """Register a throwaway component with a fake install() and a controllable
    import_name, restored after the test."""
    calls: list[str] = []

    def make(import_name):
        comp = EnvComponent(
            id="fake-pkg", label_key="env.label.fake", category="python",
            detect=lambda: DetectResult(available=True),
            install=lambda on_log: calls.append("installed"),
            import_name=import_name,
        )
        monkeypatch.setitem(env_components._BY_ID, "fake-pkg", comp)
        return comp

    yield make, calls


def test_restart_required_when_module_already_imported(fake_component, monkeypatch):
    make, _ = fake_component
    make("fake_pkg_module_already_loaded")
    monkeypatch.setitem(sys.modules, "fake_pkg_module_already_loaded", sys)  # any truthy module object
    assert env_components.install_one("fake-pkg", lambda line: None) is True


def test_restart_not_required_when_module_never_imported(fake_component, monkeypatch):
    make, _ = fake_component
    make("fake_pkg_module_never_loaded")
    monkeypatch.delitem(sys.modules, "fake_pkg_module_never_loaded", raising=False)
    assert env_components.install_one("fake-pkg", lambda line: None) is False


def test_restart_not_required_when_component_has_no_import_name(fake_component):
    make, _ = fake_component
    make(None)
    assert env_components.install_one("fake-pkg", lambda line: None) is False
