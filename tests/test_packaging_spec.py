"""packaging/core_rpc.spec — shape checks (can't exec a PyInstaller .spec file
outside a real build; SPECPATH is injected by PyInstaller itself).

Guards the module_collection_mode settings: without them, a package is zipped
into PYZ and loaded via PyInstaller's sys.meta_path frozen importer, which
CPython consults before sys.path — so the env dashboard's "update" button
installs a fresh copy into py-extra successfully but the frozen sidecar keeps
importing the stale bundled copy forever (the release-can't-update-past-its-
shipped-version bug, first found with yt-dlp). 'py' collection makes the
package a loose on-disk tree instead, resolved through the normal sys.path
PathFinder, so py-extra can genuinely shadow it. Every package the env
dashboard offers an "update" button for (core/env/components.py) needs this.
"""

from __future__ import annotations

import os

_SPEC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                      "packaging", "core_rpc.spec")


def test_env_updatable_packages_collected_as_loose_py_not_pyz():
    with open(_SPEC, "r", encoding="utf-8") as f:
        src = f.read()
    assert "module_collection_mode" in src
    assert '"yt_dlp": "py"' in src
    assert '"openai": "py"' in src
