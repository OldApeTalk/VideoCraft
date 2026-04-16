"""Tier constants for AI routing.

Phase 1 keeps plain string constants for backward compatibility with existing
callers (`tier="standard"`). The Tier helper class is a namespace convenience
for new code to use `Tier.STANDARD` without having to remember the string.
"""

TIER_PREMIUM  = "premium"
TIER_STANDARD = "standard"
TIER_ECONOMY  = "economy"
TIERS = (TIER_PREMIUM, TIER_STANDARD, TIER_ECONOMY)


class Tier:
    """Namespace for tier identifiers. Values are the same strings as TIER_*."""
    PREMIUM  = TIER_PREMIUM
    STANDARD = TIER_STANDARD
    ECONOMY  = TIER_ECONOMY
