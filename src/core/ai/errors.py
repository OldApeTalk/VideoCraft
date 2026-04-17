"""AIError contract with 9 error kinds.

Phase 1 defines the contract; providers still raise plain RuntimeError as
before. Phase 7 will add provider-specific native-exception mapping so that
feature/UI layers can branch on `e.kind`.

UI mapping (see docs/design/04-ai-router.md): each Kind has a recommended
action button that dispatches to the right remediation (AUTH -> open Router
tab, QUOTA -> switch provider, etc.).
"""

from enum import Enum


class Kind(Enum):
    NETWORK    = "network"       # DNS / TCP / TLS / timeout — retryable (transport)
    AUTH       = "auth"          # invalid / expired / revoked key — fatal
    QUOTA      = "quota"         # daily / monthly quota exhausted — fatal until reset
    RATE_LIMIT = "rate_limit"    # per-minute throttle — retryable (respect Retry-After)
    REFUSED    = "refused"       # safety filter refusal — not retryable, semantic issue
    MALFORMED  = "malformed"     # JSON schema mismatch — retryable by feature layer
    OVERFLOW   = "overflow"      # input exceeds context window — fatal for this tier
    CANCELLED  = "cancelled"     # user cancelled — via CancellationToken
    UNKNOWN    = "unknown"       # unclassified — surface raw for logs


class AIError(Exception):
    """Structured AI call error.

    Args:
        kind: one of Kind enum values.
        provider: the provider that failed (e.g. "Gemini", "DeepSeek").
        message: human-readable text safe to show users.
        retry_after: seconds the provider suggested waiting (from Retry-After
                     header when RATE_LIMIT).
        raw: original exception for logging — not meant for user display.
    """

    def __init__(self, kind: Kind, provider: str, message: str,
                 retry_after: float | None = None,
                 raw: Exception | None = None):
        super().__init__(message)
        self.kind = kind
        self.provider = provider
        self.message = message
        self.retry_after = retry_after
        self.raw = raw

    def __str__(self) -> str:
        return f"[{self.kind.value}/{self.provider}] {self.message}"
