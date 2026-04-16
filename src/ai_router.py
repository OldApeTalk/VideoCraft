"""Legacy compatibility shim — DO NOT add new code here.

The real implementation lives in `core/ai/`. All M1~M6 migrations routed
core/UI callers through the feature layer (core.translate / core.asr /
core.tts / core.srt_ops). The only remaining consumer of this shim is
TranslateApp which still imports TIER_* constants for Radiobutton values.
Once TranslateApp is converted to use plain strings or imports from a
feature-layer source, this file can be deleted.
"""

from core.ai.tiers import (
    TIER_PREMIUM,
    TIER_STANDARD,
    TIER_ECONOMY,
    TIERS,
)


__all__ = [
    "TIER_PREMIUM",
    "TIER_STANDARD",
    "TIER_ECONOMY",
    "TIERS",
]
