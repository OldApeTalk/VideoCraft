"""Configuration defaults, key file I/O, and providers.json persistence.

Split out from AIRouter so the router only orchestrates runtime state; this
module owns the on-disk format and provider catalog defaults.

Path resolution: `keys_dir()` walks up from this file's location to the
project root, then into `keys/`. Original code in src/ai_router.py went up
one level; since we're now at src/core/ai/config.py, we go up three levels.
"""

import os
import copy
import json

from core.ai.tiers import TIER_PREMIUM, TIER_STANDARD, TIER_ECONOMY


# ── Default LLM providers ────────────────────────────────────────────────────
# Provider keys must match the names used in providers.json and in legacy
# callers (e.g. srt_tools.py's AI_PROVIDERS).

_DEFAULT_PROVIDERS = {
    "Gemini": {
        "type":     "gemini",
        "key_file": "Gemini.key",
        "enabled":  True,
        "priority": 1,
        "models": [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
        ],
        "tiers": {
            TIER_PREMIUM:  "gemini-2.5-pro",
            TIER_STANDARD: "gemini-2.5-flash",
            TIER_ECONOMY:  "gemini-2.5-flash-lite",
        },
    },
    "DeepSeek": {
        "type":     "openai_compatible",
        "base_url": "https://api.deepseek.com",
        "key_file": "DeepSeek.key",
        "enabled":  True,
        "priority": 2,
        "models": [
            "deepseek-chat",
            "deepseek-reasoner",
        ],
        "tiers": {
            TIER_PREMIUM:  "deepseek-reasoner",
            TIER_STANDARD: "deepseek-chat",
            TIER_ECONOMY:  "deepseek-chat",
        },
    },
    "Custom": {
        "type":     "openai_compatible",
        "base_url": "",
        "key_file": "Custom.key",
        "enabled":  False,      # Disabled by default; user fills base_url via UI first
        "priority": 4,
        "models":   [],
        "tiers": {
            TIER_PREMIUM:  "",
            TIER_STANDARD: "",
            TIER_ECONOMY:  "",
        },
    },
    "ClaudeCode": {
        "type":       "claude_code",
        "key_file":   "",           # No API key — local `claude` CLI handles auth
        "enabled":    False,        # Off by default; user ticks Enable in Router Manager
        "priority":   3,            # Between DeepSeek(2) and Custom(4)
        "executable": "claude",     # CLI binary name or full path
        "extra_args": [],           # Advanced: additional flags for `claude -p`
        "timeout_sec": 600,
        "models": [
            "sonnet",
            "opus",
            "haiku",
        ],
        "tiers": {
            TIER_PREMIUM:  "opus",
            TIER_STANDARD: "sonnet",
            TIER_ECONOMY:  "haiku",
        },
    },
}

# ── Default tier routing ─────────────────────────────────────────────────────
# User explicitly picks (provider, model) per tier in Router UI.
# Unconfigured tier falls back to priority-based auto-selection at call time.

_DEFAULT_TIER_ROUTING = {
    TIER_PREMIUM:  {"provider": "Gemini", "model": "gemini-2.5-pro"},
    TIER_STANDARD: {"provider": "Gemini", "model": "gemini-2.5-flash"},
    TIER_ECONOMY:  {"provider": "Gemini", "model": "gemini-2.5-flash-lite"},
}

# ── Default ASR providers ────────────────────────────────────────────────────
# Kept separate from LLM providers to avoid mixing tier-routing logic.

_DEFAULT_ASR_PROVIDERS = {
    "lemonfox": {
        "name":        "LemonFox",
        "enabled":     True,
        "key_file":    "lemonfox.key",
        "base_url":    "https://api.lemonfox.ai/v1/audio/transcriptions",
        "description": "LemonFox Whisper ASR API",
        "connect_timeout_sec": 60,
        "read_timeout_sec": 120,
        "max_retries": 1,
    },
}

# ── Default TTS providers ────────────────────────────────────────────────────
# TTS needs no tier routing — just key management.

_DEFAULT_TTS_PROVIDERS = {
    "fish_audio": {
        "name":        "Fish Audio",
        "enabled":     True,
        "key_file":    "FishAudio.key",
        "description": "Fish Audio TTS — 支持音色克隆与多角色合成",
    },
}

# ── Legacy name normalization ────────────────────────────────────────────────
# SrtTools used Chinese provider names historically; map them to canonical.

_COMPAT_NAMES = {
    "自定义(OpenAI兼容)": "Custom",
}


def canonicalize_provider_name(name: str) -> str:
    """Map legacy Chinese provider names to canonical English."""
    return _COMPAT_NAMES.get(name, name)


def keys_dir() -> str:
    """Return absolute path to the repo's keys/ directory."""
    here = os.path.dirname(os.path.abspath(__file__))
    # src/core/ai -> src/core -> src -> <repo root>
    return os.path.normpath(os.path.join(here, "..", "..", "..", "keys"))


def read_key(provider_cfg: dict) -> str | None:
    """Read provider's .key file. Returns None if key_file empty/missing/blank."""
    key_file = provider_cfg.get("key_file", "")
    if not key_file:
        return None
    key_path = os.path.join(keys_dir(), key_file)
    if not os.path.exists(key_path):
        return None
    with open(key_path, "r", encoding="utf-8") as f:
        key = f.read().strip()
    return key or None


def has_auth(provider_cfg: dict) -> bool:
    """True if provider has credentials to run. claude_code relies on the
    local CLI's own login state — presence of the entry is enough.
    """
    if provider_cfg.get("type") == "claude_code":
        return True
    return read_key(provider_cfg) is not None


# ── Persistence ──────────────────────────────────────────────────────────────

def load_config() -> dict:
    """Load providers.json, applying defaults + migrations. Writes back on
    first run or when schema migration triggered a fix.

    Returns dict with keys: providers / asr_providers / tts_providers / tier_routing.
    """
    cfg_path = os.path.join(keys_dir(), "providers.json")
    if os.path.exists(cfg_path):
        with open(cfg_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        providers     = data.get("providers",     {})
        asr_providers = data.get("asr_providers", copy.deepcopy(_DEFAULT_ASR_PROVIDERS))
        tts_providers = data.get("tts_providers", copy.deepcopy(_DEFAULT_TTS_PROVIDERS))
        tier_routing  = data.get("tier_routing",  copy.deepcopy(_DEFAULT_TIER_ROUTING))
        wrote_on_first_run = False
    else:
        providers     = copy.deepcopy(_DEFAULT_PROVIDERS)
        asr_providers = copy.deepcopy(_DEFAULT_ASR_PROVIDERS)
        tts_providers = copy.deepcopy(_DEFAULT_TTS_PROVIDERS)
        tier_routing  = copy.deepcopy(_DEFAULT_TIER_ROUTING)
        wrote_on_first_run = True
        # First-run write happens below after migrations run

    providers, tier_routing, migrated = _migrate_removed_providers(
        providers, tier_routing
    )
    providers, normalized = _normalize_providers(providers)
    asr_providers = _normalize_asr_providers(asr_providers)

    result = {
        "providers":     providers,
        "asr_providers": asr_providers,
        "tts_providers": tts_providers,
        "tier_routing":  tier_routing,
    }

    if wrote_on_first_run or migrated or normalized:
        save_config(result)

    return result


def save_config(data: dict) -> None:
    """Write providers.json. Creates the keys/ directory if missing."""
    cfg_path = os.path.join(keys_dir(), "providers.json")
    os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
    with open(cfg_path, "w", encoding="utf-8") as f:
        json.dump({
            "tier_routing":  data["tier_routing"],
            "providers":     data["providers"],
            "asr_providers": data["asr_providers"],
            "tts_providers": data["tts_providers"],
        }, f, ensure_ascii=False, indent=2)


# ── Schema migrations ────────────────────────────────────────────────────────

def _migrate_removed_providers(providers: dict, tier_routing: dict):
    """Drop providers that were removed in newer versions.

    Groq was removed because its Llama/gpt-oss/qwen models did not meet
    VideoCraft's NLP quality bar. Old providers.json files still carrying
    it are cleaned up here; tier_routing pointing at Groq reverts to
    the default (Gemini).
    """
    removed = ["Groq"]
    dirty = False
    for name in removed:
        if name in providers:
            providers.pop(name, None)
            dirty = True

    for tier, routing in list(tier_routing.items()):
        if routing.get("provider") in removed:
            tier_routing[tier] = copy.deepcopy(
                _DEFAULT_TIER_ROUTING.get(tier, {"provider": "Gemini", "model": ""})
            )
            dirty = True

    return providers, tier_routing, dirty


def _normalize_providers(providers: dict):
    """Backfill provider entries added in newer versions (e.g. ClaudeCode).

    Users upgrading from a previous release would otherwise not see newly
    introduced providers in their Router Manager because their providers.json
    only carries the providers that existed when it was written.
    """
    dirty = False
    for name, default_cfg in _DEFAULT_PROVIDERS.items():
        if name not in providers:
            providers[name] = copy.deepcopy(default_cfg)
            dirty = True
    return providers, dirty


def _normalize_asr_providers(asr_providers: dict) -> dict:
    """Backfill missing fields on ASR providers for backward compat."""
    for name, default_cfg in _DEFAULT_ASR_PROVIDERS.items():
        current = asr_providers.setdefault(name, copy.deepcopy(default_cfg))
        for key, value in default_cfg.items():
            current.setdefault(key, value)
    return asr_providers
