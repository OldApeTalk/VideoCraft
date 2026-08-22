# PyInstaller spec for the VideoCraft core_rpc sidecar (P3, packaging-design.md §2.2).
#
# onedir build → dist/core_rpc/core_rpc.exe + _internal/. build_sidecar.ps1 copies
# the result into desktop/resources/sidecar/, which electron-builder bundles as an
# extraResource. Run from the repo root inside the clean base build venv:
#   python -m PyInstaller --noconfirm --clean packaging/core_rpc.spec
#
# The sidecar imports core/* and (via core_rpc.methods.load_plugins) the plugin
# trees dynamically; PyInstaller's static analysis misses those, so we collect the
# whole packages as hiddenimports.

import os

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# SPECPATH = this spec's dir (packaging/); the repo root is its parent.
REPO = os.path.dirname(SPECPATH)  # noqa: F821  (SPECPATH injected by PyInstaller)
SRC = os.path.join(REPO, "src")

hiddenimports = (
    collect_submodules("core")
    + collect_submodules("creations")
    + collect_submodules("materials")
    + collect_submodules("core_rpc")
    # pip is bundled so `core_rpc.exe --vc-pip` can install opt-in extras at
    # runtime (sidecar_entry.py / packaging-design.md §5.3). collect_submodules
    # pulls pip._internal + its vendored deps that static analysis misses.
    + collect_submodules("pip")
    # HTTP transport (ADR-0010). uvicorn loads its protocol/loop/lifespan
    # implementations by dotted-string at runtime — static analysis misses them,
    # so collect the whole packages. fastapi/starlette are mostly static but
    # collected for safety (and to pull starlette's optional bits we touch).
    + collect_submodules("uvicorn")
    + collect_submodules("fastapi")
    + collect_submodules("starlette")
    # i18n.py is a top-level module (src/i18n.py), not under a collected package;
    # core.subtitle_check / translate / asr import it lazily for their messages.
    + ["i18n"]
)

# Non-.py runtime data the modules read (e.g. i18n / language / catalog JSON).
# pip ships data files (vendored cacert.pem, etc.) it needs at runtime.
datas = (
    collect_data_files("core", includes=["**/*.json", "**/*.txt"])
    + collect_data_files("pip")
    # i18n locale tables — read at runtime by i18n.tr (src/i18n/<code>.json).
    # Without these the frozen sidecar returns raw keys for every tr() message
    # (e.g. the subtitle-check report). Land them at <_MEIPASS>/i18n/ to match
    # i18n.LOCALE_DIR's frozen branch.
    + [
        (os.path.join(SRC, "i18n", "zh.json"), "i18n"),
        (os.path.join(SRC, "i18n", "en.json"), "i18n"),
    ]
)

a = Analysis(
    # Entry is a wrapper that imports core_rpc.server as a package member, so the
    # sidecar's relative imports resolve under freeze (packaging/sidecar_entry.py).
    [os.path.join(REPO, "packaging", "sidecar_entry.py")],
    pathex=[REPO, SRC],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Heavy deps that are NOT in the base closure (opt-in or removed) — exclude so
    # a stray transitive reference can't drag them in. tkinter is gone post-P2.
    excludes=[
        "torch",
        "sherpa_onnx",
        "onnxruntime",
        "pandas",
        "pyarrow",
        "wandb",
        "transformers",
        "tkinter",
    ],
    # yt-dlp is the one bundled package the env dashboard's "update" button must
    # actually be able to shadow (it's the only dep that must track upstream —
    # packaging-design.md §5.3). Default collection zips pure-Python deps into
    # PYZ, loaded via PyInstaller's own sys.meta_path frozen importer — which
    # CPython consults BEFORE sys.path, so prepending py-extra there can never
    # shadow it (a runtime "upgrade" would report success and even show the new
    # version, while every `import yt_dlp` still silently got the frozen old
    # copy — the release-can't-update bug). 'py' collects it as loose source
    # files instead, resolved through the normal sys.path PathFinder like any
    # on-disk package, so py-extra's copy — prepended at sys.path[0] — wins for
    # real, including its own submodule imports (setting propagates to the
    # whole yt_dlp.* subtree, see PyInstaller's _get_module_collection_mode).
    # openai gets the same treatment: it's another env-dashboard "update"
    # target (upgrade_pip("openai") in core/env/components.py) — same
    # meta_path-vs-sys.path shadowing bug would otherwise apply to it too.
    module_collection_mode={"yt_dlp": "py", "openai": "py"},
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="core_rpc",
    console=True,  # stdout carries the VC_RPC_PORT handshake + stderr logs.
    disable_windowed_traceback=False,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="core_rpc",
)
