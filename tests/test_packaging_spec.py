"""packaging/core_rpc.spec — shape checks (can't exec a PyInstaller .spec file
outside a real build; SPECPATH is injected by PyInstaller itself).

Guards the yt_dlp module_collection_mode setting: without it, yt_dlp is zipped
into PYZ and loaded via PyInstaller's sys.meta_path frozen importer, which
CPython consults before sys.path — so the env dashboard's "update yt-dlp" button
installs into py-extra successfully but the frozen sidecar keeps importing the
stale bundled copy forever (the release-can't-update-past-its-shipped-version
bug). 'py' collection makes yt_dlp a loose on-disk package so the normal
sys.path-based PathFinder resolves it, letting py-extra actually shadow it.
"""

from __future__ import annotations

import os

_SPEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "packaging", "core_rpc.spec")


def test_yt_dlp_collected_as_loose_py_not_pyz():
    with open(_SPEC, "r", encoding="utf-8") as f:
        src = f.read()
    assert "module_collection_mode" in src
    assert '"yt_dlp": "py"' in src
