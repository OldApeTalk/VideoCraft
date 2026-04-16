"""Legacy compatibility shim — DO NOT add new code here.

The real implementation now lives in `core/ai/`. New code MUST use the
feature-layer facade (e.g. `from core import ai`) or, for infrastructure
tools like the Router UI, directly import from `core.ai`.

This shim is kept because the following callers still use the old
`from ai_router import ...` pattern:
  - tools/translate/translate_srt.py
  - tools/subtitle/srt_tools.py
  - tools/text2video/text2video.py
  - tools/speech/speech2text.py
  - core/srt_ops.py
  - router_manager.py (also imports _keys_dir)

Each of these migrates to the feature layer in a later milestone (M2-M5)
and this file can be removed after they're all converted.
"""

# Re-export the singleton and tier constants.
from core.ai import router
from core.ai.router import AIRouter
from core.ai.tiers import (
    TIER_PREMIUM,
    TIER_STANDARD,
    TIER_ECONOMY,
    TIERS,
)

# Legacy name: router_manager.py imports `_keys_dir` to locate the keys/
# directory. The canonical name in core.ai.config is `keys_dir` (no
# underscore prefix) since it's now a module-level public helper — but we
# alias it here to preserve the old import.
from core.ai.config import keys_dir as _keys_dir


__all__ = [
    "router",
    "AIRouter",
    "TIER_PREMIUM",
    "TIER_STANDARD",
    "TIER_ECONOMY",
    "TIERS",
    "_keys_dir",
]
