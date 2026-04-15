"""
ai_router.py - VideoCraft 统一 AI 路由层

功能：
  - 基于 tier（档位）的路由：premium / standard / economy
  - 用户可在管理界面为每个档位明确指定 Provider + Model
  - 自动降级（tier_routing 中的 provider 不可用时回落到优先级路由）
  - 线程安全的调用统计（in-memory，供 UI 状态栏展示）
  - 读取现有 keys/*.key 文件，兼容现有模块
  - 首次运行时自动生成 keys/providers.json

使用方式：
    from ai_router import router

    # 按档位路由（router 按 tier_routing 配置决定用哪个 provider）
    text = router.complete("请翻译这段话", tier="standard")

    # 显式指定 provider + model（UI 下拉框直接选择时使用）
    text = router.complete("请翻译", provider="Gemini", model="gemini-2.5-flash")
"""

import os
import json
import copy
import subprocess
import threading
from datetime import datetime

# ── 档位常量 ──────────────────────────────────────────────────────────────────

TIER_PREMIUM  = "premium"
TIER_STANDARD = "standard"
TIER_ECONOMY  = "economy"
TIERS = (TIER_PREMIUM, TIER_STANDARD, TIER_ECONOMY)

# ── 默认 Provider 配置 ────────────────────────────────────────────────────────
# provider 名与 SrtTools.py 的 AI_PROVIDERS key 保持一致，便于直接传入

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
        "enabled":  False,      # Disabled by default; user fills in base_url via UI first
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
        "key_file":   "",           # No API key — the local `claude` CLI handles auth itself
        "enabled":    False,        # Off by default; user must tick Enable in the Router Manager
        "priority":   3,            # Between DeepSeek(2) and Custom(4): auto-fallback candidate
                                    # once explicitly enabled by the user
        "executable": "claude",     # CLI binary name or full path
        "extra_args": [],           # Advanced: additional flags to pass through to `claude -p`
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

# ── 默认档位路由 ──────────────────────────────────────────────────────────────
# 用户在管理界面明确指定每个档位使用的 provider + model
# 未配置时回落到按 priority 自动选择

_DEFAULT_TIER_ROUTING = {
    TIER_PREMIUM:  {"provider": "Gemini", "model": "gemini-2.5-pro"},
    TIER_STANDARD: {"provider": "Gemini", "model": "gemini-2.5-flash"},
    TIER_ECONOMY:  {"provider": "Gemini", "model": "gemini-2.5-flash-lite"},
}

# ── 默认 ASR Provider 配置 ────────────────────────────────────────────────────
# 与 LLM providers 分开，避免混入 tier routing 逻辑
# 未来可在此添加更多 ASR 提供商（如 OpenAI Whisper、Groq Audio 等）

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

# ── 默认 TTS Provider 配置 ────────────────────────────────────────────────────
# TTS 无需 tier routing，只需 key 管理

_DEFAULT_TTS_PROVIDERS = {
    "fish_audio": {
        "name":        "Fish Audio",
        "enabled":     True,
        "key_file":    "FishAudio.key",
        "description": "Fish Audio TTS — 支持音色克隆与多角色合成",
    },
}

# 兼容 SrtTools 的中文 provider 名
_COMPAT_NAMES = {
    "自定义(OpenAI兼容)": "Custom",
}


def _keys_dir() -> str:
    """返回 keys/ 目录的绝对路径（src/ 的上一级）。"""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "keys")


# ── AIRouter ──────────────────────────────────────────────────────────────────

class AIRouter:
    """
    进程内单例 AI 路由器，通过模块级 `router` 对象访问。

    线程安全：多个工作线程可同时调用 complete()，统计数据通过 Lock 保护。
    """

    def __init__(self):
        self._lock           = threading.Lock()
        self._providers:      dict = {}
        self._asr_providers:  dict = {}
        self._tts_providers:  dict = {}
        self._tier_routing:   dict = {}
        self._stats:          dict = {}
        self._load_config()

    # ── 公开 API ──────────────────────────────────────────────────────────────

    def complete(self, prompt: str, *,
                 tier: str = TIER_STANDARD,
                 provider: str = None,
                 model: str = None) -> str:
        """
        调用 AI 生成文本。

        Args:
            prompt:   输入提示词。
            tier:     "premium" | "standard" | "economy"。
                      未指定 provider 时，按 tier_routing 或 priority 选 provider。
            provider: 指定 provider（如 "Gemini"）。指定后 tier 仅用于查找默认 model。
            model:    指定模型 ID，覆盖所有默认值。

        Returns:
            AI 生成的文本字符串。

        Raises:
            RuntimeError: 所有候选 provider 均失败时抛出。
        """
        if tier not in TIERS:
            raise ValueError(f"tier 必须是 {TIERS} 之一，收到: {tier!r}")

        if provider:
            provider = _COMPAT_NAMES.get(provider, provider)
            return self._complete_explicit(provider, tier, model, prompt)
        else:
            return self._complete_by_tier(tier, model, prompt)

    def complete_json(self, prompt: str, *,
                      schema: dict,
                      tier: str = TIER_STANDARD,
                      provider: str = None,
                      model: str = None) -> dict:
        """Structured JSON completion. The model is constrained to return a
        JSON object matching the given schema; the router parses it and returns
        a plain dict.

        Args:
            prompt:   The user prompt. The schema is injected by the router as
                      a system hint or native response_schema flag, so callers
                      should NOT manually repeat schema instructions in prompt.
            schema:   JSON Schema dict (OpenAPI-style) describing the expected
                      structure.
            tier:     "premium" | "standard" | "economy".
            provider: Optional explicit provider name.
            model:    Optional explicit model ID.

        Returns:
            Parsed JSON response as a dict.

        Raises:
            RuntimeError: API call failed, response was not valid JSON, or
                          none of the candidate providers succeeded.
        """
        if tier not in TIERS:
            raise ValueError(f"tier 必须是 {TIERS} 之一，收到: {tier!r}")
        if not isinstance(schema, dict):
            raise ValueError(f"schema 必须是 dict，收到: {type(schema).__name__}")

        if provider:
            provider = _COMPAT_NAMES.get(provider, provider)
            return self._complete_json_explicit(provider, tier, model, prompt, schema)
        else:
            return self._complete_json_by_tier(tier, model, prompt, schema)

    def get_stats(self) -> dict:
        """返回当前调用统计的深拷贝（线程安全）。"""
        with self._lock:
            return copy.deepcopy(self._stats)

    def get_tier_routing(self) -> dict:
        """返回当前档位路由配置的深拷贝。
        结构: {"premium": {"provider": "Gemini", "model": "..."}, ...}
        """
        return copy.deepcopy(self._tier_routing)

    def set_tier_routing(self, tier: str, provider: str, model: str):
        """为某个档位设置 provider + model，并持久化到 providers.json。"""
        if tier not in TIERS:
            raise ValueError(f"tier 必须是 {TIERS} 之一")
        self._tier_routing[tier] = {"provider": provider, "model": model}
        self._save_config()

    def get_provider_names(self) -> list:
        """返回所有已配置的 provider 名称列表。"""
        return list(self._providers.keys())

    def get_provider_models(self, provider: str) -> list:
        """返回指定 provider 的模型列表。"""
        provider = _COMPAT_NAMES.get(provider, provider)
        return self._providers.get(provider, {}).get("models", [])

    def get_available_providers(self, tier: str = None) -> list:
        """Return providers that are enabled AND have valid auth for their type.
        For claude_code, the local `claude` CLI handles its own auth, so no key
        file is required — presence of the entry + enabled flag is enough."""
        result = []
        for name, cfg in self._providers.items():
            if not cfg.get("enabled", True):
                continue
            if not self._has_auth(cfg):
                continue
            model_id = cfg["tiers"].get(tier) if tier else None
            if tier and not model_id:
                continue
            result.append({
                "name":     name,
                "type":     cfg["type"],
                "priority": cfg.get("priority", 99),
                "model":    model_id,
            })
        result.sort(key=lambda x: x["priority"])
        return result

    def reload_config(self):
        """重新从 providers.json 加载配置（热重载）。"""
        self._load_config()

    # ── ASR 公开 API ──────────────────────────────────────────────────────────

    def get_asr_key(self, provider: str) -> str | None:
        """返回指定 ASR provider 的 API key。key 未配置时返回 None。"""
        cfg = self._asr_providers.get(provider)
        if cfg is None:
            return None
        return self._read_key(cfg)

    def get_asr_config(self, provider: str) -> dict | None:
        """返回指定 ASR provider 的完整配置（深拷贝）。"""
        cfg = self._asr_providers.get(provider)
        return copy.deepcopy(cfg) if cfg else None

    def get_available_asr_providers(self) -> list:
        """返回已启用的 ASR providers 列表，附带 key 是否存在的状态。"""
        result = []
        for name, cfg in self._asr_providers.items():
            result.append({
                "name":     name,
                "display":  cfg.get("name", name),
                "enabled":  cfg.get("enabled", True),
                "has_key":  self._read_key(cfg) is not None,
                "base_url": cfg.get("base_url", ""),
            })
        return result

    def update_asr_provider(self, provider: str, **kwargs):
        """更新 ASR provider 的配置字段并持久化。"""
        if provider not in self._asr_providers:
            raise RuntimeError(f"未知 ASR provider: {provider!r}")
        self._asr_providers[provider].update(kwargs)
        self._save_config()

    # ── TTS 公开 API ──────────────────────────────────────────────────────────

    def get_tts_key(self, provider: str) -> str | None:
        """返回指定 TTS provider 的 API key。key 未配置时返回 None。"""
        cfg = self._tts_providers.get(provider)
        if cfg is None:
            return None
        return self._read_key(cfg)

    def get_tts_config(self, provider: str) -> dict | None:
        """返回指定 TTS provider 的完整配置（深拷贝）。"""
        cfg = self._tts_providers.get(provider)
        return copy.deepcopy(cfg) if cfg else None

    def get_available_tts_providers(self) -> list:
        """返回已启用的 TTS providers 列表，附带 key 是否存在的状态。"""
        return [
            {
                "name":    name,
                "display": cfg.get("name", name),
                "enabled": cfg.get("enabled", True),
                "has_key": self._read_key(cfg) is not None,
            }
            for name, cfg in self._tts_providers.items()
        ]

    def update_tts_provider(self, provider: str, **kwargs):
        """更新 TTS provider 的配置字段并持久化。"""
        if provider not in self._tts_providers:
            raise RuntimeError(f"未知 TTS provider: {provider!r}")
        self._tts_providers[provider].update(kwargs)
        self._save_config()

    def set_provider_enabled(self, provider: str, enabled: bool):
        """运行时启用/禁用某个 provider，并持久化。"""
        provider = _COMPAT_NAMES.get(provider, provider)
        if provider in self._providers:
            self._providers[provider]["enabled"] = enabled
            self._save_config()

    def update_provider(self, provider: str, **kwargs):
        """
        更新 provider 的任意配置字段并持久化。

        示例：
            router.update_provider("Custom", base_url="http://...", enabled=True)
            router.update_provider("DeepSeek", models=["deepseek-chat", "deepseek-reasoner"])
        """
        provider = _COMPAT_NAMES.get(provider, provider)
        if provider not in self._providers:
            raise RuntimeError(f"未知 provider: {provider!r}")
        cfg = self._providers[provider]
        for k, v in kwargs.items():
            cfg[k] = v          # 允许新增字段，不限于已有字段
        self._save_config()

    # ── 内部路由逻辑 ──────────────────────────────────────────────────────────

    def _complete_explicit(self, provider: str, tier: str, model: str, prompt: str) -> str:
        """指定 provider 时的调用路径。"""
        cfg = self._providers.get(provider)
        if cfg is None:
            raise RuntimeError(f"未知 provider: {provider!r}，请检查 providers.json")
        resolved_model = model or cfg["tiers"].get(tier) or cfg["tiers"].get(TIER_STANDARD)
        if not resolved_model:
            raise RuntimeError(f"provider {provider!r} 在 tier={tier!r} 下没有配置模型")
        return self._call(provider, cfg, resolved_model, prompt)

    def _complete_by_tier(self, tier: str, model: str, prompt: str) -> str:
        """
        按 tier 路由：
        1. 优先使用用户在管理界面明确配置的 tier_routing
        2. 若配置的 provider 不可用，回落到按 priority 自动选择并降级
        """
        routing = self._tier_routing.get(tier, {})
        r_provider = routing.get("provider", "")
        r_model    = model or routing.get("model", "")

        if r_provider and r_model:
            cfg = self._providers.get(r_provider)
            if cfg and cfg.get("enabled", True) and self._read_key(cfg) is not None:
                try:
                    return self._call(r_provider, cfg, r_model, prompt)
                except Exception:
                    pass  # 明确配置的 provider 失败 → 回落

        # 回落：按 priority 排序逐个尝试
        candidates = self._get_candidates(tier)
        if not candidates:
            raise RuntimeError(
                f"没有可用的 provider 支持 tier={tier!r}，"
                "请在 AI Router 管理界面配置 API Key。"
            )
        last_err = None
        for name, cfg, mid in candidates:
            try:
                return self._call(name, cfg, model or mid, prompt)
            except Exception as e:
                last_err = e

        raise RuntimeError(
            f"所有 tier={tier!r} 的 provider 均失败。最后错误: {last_err}"
        )

    def _complete_json_explicit(self, provider: str, tier: str, model: str,
                                 prompt: str, schema: dict) -> dict:
        """JSON variant of _complete_explicit."""
        cfg = self._providers.get(provider)
        if cfg is None:
            raise RuntimeError(f"未知 provider: {provider!r}，请检查 providers.json")
        resolved_model = model or cfg["tiers"].get(tier) or cfg["tiers"].get(TIER_STANDARD)
        if not resolved_model:
            raise RuntimeError(f"provider {provider!r} 在 tier={tier!r} 下没有配置模型")
        return self._call_json(provider, cfg, resolved_model, prompt, schema)

    def _complete_json_by_tier(self, tier: str, model: str,
                                prompt: str, schema: dict) -> dict:
        """JSON variant of _complete_by_tier."""
        routing = self._tier_routing.get(tier, {})
        r_provider = routing.get("provider", "")
        r_model    = model or routing.get("model", "")

        if r_provider and r_model:
            cfg = self._providers.get(r_provider)
            if cfg and cfg.get("enabled", True) and self._read_key(cfg) is not None:
                try:
                    return self._call_json(r_provider, cfg, r_model, prompt, schema)
                except Exception:
                    pass

        candidates = self._get_candidates(tier)
        if not candidates:
            raise RuntimeError(
                f"没有可用的 provider 支持 tier={tier!r}，"
                "请在 AI Router 管理界面配置 API Key。"
            )
        last_err = None
        for name, cfg, mid in candidates:
            try:
                return self._call_json(name, cfg, model or mid, prompt, schema)
            except Exception as e:
                last_err = e

        raise RuntimeError(
            f"所有 tier={tier!r} 的 provider 均失败。最后错误: {last_err}"
        )

    def _get_candidates(self, tier: str) -> list:
        """返回按 priority 排序的 (name, cfg, model_id) 列表，跳过不可用项。"""
        result = []
        for name, cfg in self._providers.items():
            if not cfg.get("enabled", True):
                continue
            model_id = cfg["tiers"].get(tier, "")
            if not model_id:
                continue
            if not self._has_auth(cfg):
                continue
            result.append((name, cfg, model_id, cfg.get("priority", 99)))
        result.sort(key=lambda x: x[3])
        return [(n, c, m) for n, c, m, _ in result]

    @staticmethod
    def _has_auth(cfg: dict) -> bool:
        """Return True if the provider has the credentials needed to run.
        claude_code providers rely on the local CLI's own login state, so
        presence of the entry is sufficient; all other types require a
        non-empty key file."""
        if cfg.get("type") == "claude_code":
            return True
        return AIRouter._read_key(cfg) is not None

    # ── Provider 调用层 ───────────────────────────────────────────────────────

    def _call(self, name: str, cfg: dict, model_id: str, prompt: str) -> str:
        """调用指定 provider，记录统计。失败时抛出异常（调用方决定是否降级）。"""
        ptype = cfg.get("type")
        api_key = None
        if ptype != "claude_code":
            api_key = self._read_key(cfg)
            if api_key is None:
                raise RuntimeError(f"API Key 未配置: {cfg.get('key_file', '?')}")

        try:
            if ptype == "gemini":
                result = self._call_gemini(api_key, model_id, prompt)
            elif ptype == "openai_compatible":
                base_url = cfg.get("base_url", "")
                if not base_url:
                    raise RuntimeError(f"provider {name!r} 的 base_url 未配置")
                result = self._call_openai(api_key, base_url, model_id, prompt)
            elif ptype == "claude_code":
                result = self._call_claude_code(cfg, model_id, prompt)
            else:
                raise RuntimeError(f"不支持的 provider 类型: {ptype!r}")

            self._record(name, success=True)
            return result

        except Exception as e:
            self._record(name, success=False, error=str(e))
            raise

    def _call_gemini(self, api_key: str, model_id: str, prompt: str) -> str:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_id)
        response = model.generate_content(prompt)
        return response.text.strip()

    def _call_openai(self, api_key: str, base_url: str, model_id: str, prompt: str) -> str:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()

    # ── Provider 调用层（JSON）────────────────────────────────────────────────

    def _call_json(self, name: str, cfg: dict, model_id: str,
                   prompt: str, schema: dict) -> dict:
        """Structured JSON dispatch. Mirrors _call() but routes to JSON-capable
        provider implementations. Records stats; raises on failure."""
        ptype = cfg.get("type")
        api_key = None
        if ptype != "claude_code":
            api_key = self._read_key(cfg)
            if api_key is None:
                raise RuntimeError(f"API Key 未配置: {cfg.get('key_file', '?')}")

        try:
            if ptype == "gemini":
                result = self._call_gemini_json(api_key, model_id, prompt, schema)
            elif ptype == "openai_compatible":
                base_url = cfg.get("base_url", "")
                if not base_url:
                    raise RuntimeError(f"provider {name!r} 的 base_url 未配置")
                result = self._call_openai_json(api_key, base_url, model_id, prompt, schema)
            elif ptype == "claude_code":
                result = self._call_claude_code_json(cfg, model_id, prompt, schema)
            else:
                raise RuntimeError(f"不支持的 JSON provider 类型: {ptype!r}")

            self._record(name, success=True)
            return result

        except Exception as e:
            self._record(name, success=False, error=str(e))
            raise

    def _call_gemini_json(self, api_key: str, model_id: str,
                           prompt: str, schema: dict) -> dict:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(
            model_id,
            generation_config={
                "response_mime_type": "application/json",
                "response_schema": schema,
            },
        )
        response = model.generate_content(prompt)
        raw = (response.text or "").strip()
        return self._parse_json_response(raw, provider_hint="Gemini")

    def _call_openai_json(self, api_key: str, base_url: str, model_id: str,
                           prompt: str, schema: dict) -> dict:
        from openai import OpenAI
        client = OpenAI(api_key=api_key, base_url=base_url)
        schema_hint = (
            "You must respond with a single JSON object that strictly matches "
            "this JSON Schema:\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
            "Return only the JSON object. No markdown fences. No prose. No explanations."
        )
        response = client.chat.completions.create(
            model=model_id,
            messages=[
                {"role": "system", "content": schema_hint},
                {"role": "user",   "content": prompt},
            ],
            response_format={"type": "json_object"},
        )
        raw = (response.choices[0].message.content or "").strip()
        return self._parse_json_response(raw, provider_hint="OpenAI-compatible")

    @staticmethod
    def _strip_json_fence(raw: str) -> str:
        """Strip ```json ... ``` or ``` ... ``` fences some models wrap JSON in.
        Returns the inner content trimmed. Leaves non-fenced input untouched."""
        s = raw.strip()
        if not s.startswith("```"):
            return s
        # Drop opening fence (optionally with language tag) and closing fence.
        lines = s.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        return "\n".join(lines).strip()

    @classmethod
    def _parse_json_response(cls, raw: str, *, provider_hint: str) -> dict:
        """Clean markdown fences and json.loads. Raises RuntimeError with a
        short snippet of the raw output on failure so callers can debug."""
        cleaned = cls._strip_json_fence(raw)
        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as e:
            snippet = cleaned[:300].replace("\n", "\\n")
            raise RuntimeError(
                f"{provider_hint} returned non-JSON output: {e}. "
                f"Raw (first 300 chars): {snippet!r}"
            )
        if not isinstance(parsed, dict):
            raise RuntimeError(
                f"{provider_hint} returned non-object JSON "
                f"(type={type(parsed).__name__}): {str(parsed)[:200]!r}"
            )
        return parsed

    # ── Provider 调用层（Claude Code CLI）─────────────────────────────────────

    def _call_claude_code(self, cfg: dict, model_id: str, prompt: str) -> str:
        """Run the local `claude` CLI headless and return plain text stdout.

        The prompt is piped over stdin to avoid Windows' ~32KB command-line
        length ceiling. --permission-mode bypassPermissions is safe here
        because we never ask the model to use Write/Edit; we only consume
        its text output."""
        cmd = self._claude_code_cmd(cfg, model_id, output_format="text")
        return self._run_claude_subprocess(cmd, cfg, prompt)

    def _call_claude_code_json(self, cfg: dict, model_id: str,
                                prompt: str, schema: dict) -> dict:
        """Run the local `claude` CLI and parse structured JSON out of it.

        Uses --output-format json, which wraps the model's text in a result
        envelope: {"type":"result","subtype":"success","result":"...","cost_usd":...}.
        The envelope's `result` field is the model's raw text; since we ask
        the model to emit JSON, we have to parse that string a second time."""
        cmd = self._claude_code_cmd(cfg, model_id, output_format="json")
        full_prompt = (
            f"{prompt}\n\n"
            "Respond with ONLY a single JSON object that strictly matches "
            "this JSON Schema:\n"
            f"{json.dumps(schema, ensure_ascii=False, indent=2)}\n"
            "No prose. No markdown. No code fences. Just the JSON object."
        )
        envelope_raw = self._run_claude_subprocess(cmd, cfg, full_prompt)

        try:
            envelope = json.loads(envelope_raw)
        except json.JSONDecodeError:
            raise RuntimeError(
                f"ClaudeCode CLI returned non-JSON stdout: {envelope_raw[:300]!r}"
            )
        inner_text = envelope.get("result", "")
        if not inner_text:
            raise RuntimeError(
                f"ClaudeCode result envelope missing 'result' field: "
                f"{str(envelope)[:200]!r}"
            )
        return self._parse_json_response(inner_text, provider_hint="ClaudeCode")

    @staticmethod
    def _claude_code_cmd(cfg: dict, model_id: str, *, output_format: str) -> list:
        """Build the argv list for a headless `claude -p` invocation."""
        executable = cfg.get("executable") or "claude"
        cmd = [
            executable, "-p",
            "--output-format", output_format,
            "--permission-mode", "bypassPermissions",
        ]
        if model_id:
            cmd += ["--model", model_id]
        extra = cfg.get("extra_args") or []
        if extra:
            cmd += list(extra)
        return cmd

    @staticmethod
    def _run_claude_subprocess(cmd: list, cfg: dict, prompt: str) -> str:
        """Spawn the Claude CLI subprocess with prompt on stdin, return stdout.
        Raises RuntimeError on missing binary, timeout, or non-zero exit."""
        executable = cmd[0] if cmd else "claude"
        try:
            result = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=int(cfg.get("timeout_sec", 600)),
            )
        except FileNotFoundError:
            raise RuntimeError(
                f"Claude Code CLI not found: {executable!r}. "
                "Install from https://claude.com/claude-code and ensure it "
                "is on PATH, or set a full path in the Router Manager."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError(
                f"Claude Code CLI timed out after {cfg.get('timeout_sec')}s"
            )
        if result.returncode != 0:
            tail = (result.stderr or "").strip().splitlines()[-10:]
            raise RuntimeError("claude code failed: " + " | ".join(tail))
        return (result.stdout or "").strip()

    # ── 统计 ──────────────────────────────────────────────────────────────────

    def _record(self, name: str, success: bool, error: str = None):
        with self._lock:
            s = self._stats.setdefault(name, {
                "calls": 0, "errors": 0,
                "last_error": None, "last_used": None,
            })
            s["calls"] += 1
            s["last_used"] = datetime.now().isoformat(timespec="seconds")
            if not success:
                s["errors"] += 1
                s["last_error"] = error

    # ── 配置加载/持久化 ───────────────────────────────────────────────────────

    def _load_config(self):
        cfg_path = os.path.join(_keys_dir(), "providers.json")
        if os.path.exists(cfg_path):
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._providers      = data.get("providers",      {})
            self._asr_providers  = data.get("asr_providers",  copy.deepcopy(_DEFAULT_ASR_PROVIDERS))
            self._tts_providers  = data.get("tts_providers",  copy.deepcopy(_DEFAULT_TTS_PROVIDERS))
            self._tier_routing   = data.get("tier_routing",   copy.deepcopy(_DEFAULT_TIER_ROUTING))
        else:
            self._providers      = copy.deepcopy(_DEFAULT_PROVIDERS)
            self._asr_providers  = copy.deepcopy(_DEFAULT_ASR_PROVIDERS)
            self._tts_providers  = copy.deepcopy(_DEFAULT_TTS_PROVIDERS)
            self._tier_routing   = copy.deepcopy(_DEFAULT_TIER_ROUTING)
            self._save_config()     # 首次运行写出默认配置

        self._migrate_removed_providers()
        self._normalize_providers()
        self._normalize_asr_providers()

        # 初始化统计条目
        with self._lock:
            for name in self._providers:
                self._stats.setdefault(name, {
                    "calls": 0, "errors": 0,
                    "last_error": None, "last_used": None,
                })

    def _save_config(self):
        cfg_path = os.path.join(_keys_dir(), "providers.json")
        os.makedirs(os.path.dirname(cfg_path), exist_ok=True)
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump({
                "tier_routing":  self._tier_routing,
                "providers":     self._providers,
                "asr_providers": self._asr_providers,
                "tts_providers": self._tts_providers,
            }, f, ensure_ascii=False, indent=2)

    def _migrate_removed_providers(self):
        """Clean up providers that were removed in newer versions.

        Groq was removed because its Llama/gpt-oss/qwen models did not meet
        VideoCraft's NLP quality bar. If an old providers.json still has it,
        drop the entry and rewrite any tier_routing that pointed at it back to
        the default (Gemini).
        """
        removed = ["Groq"]
        dirty = False
        for name in removed:
            if name in self._providers:
                self._providers.pop(name, None)
                dirty = True
            if name in self._stats:
                self._stats.pop(name, None)

        default_routing = _DEFAULT_TIER_ROUTING
        for tier, routing in list(self._tier_routing.items()):
            if routing.get("provider") in removed:
                self._tier_routing[tier] = copy.deepcopy(
                    default_routing.get(tier, {"provider": "Gemini", "model": ""})
                )
                dirty = True

        if dirty:
            self._save_config()

    def _normalize_providers(self):
        """Backfill provider entries that are missing from an older providers.json.

        When a new release adds a provider to _DEFAULT_PROVIDERS (e.g. ClaudeCode),
        users upgrading from a previous version would otherwise not see it in
        their Router Manager because the existing providers.json only carries
        the providers known at creation time. We insert any missing defaults
        verbatim and persist."""
        dirty = False
        for name, default_cfg in _DEFAULT_PROVIDERS.items():
            if name not in self._providers:
                self._providers[name] = copy.deepcopy(default_cfg)
                dirty = True
        if dirty:
            self._save_config()

    def _normalize_asr_providers(self):
        """回填 ASR provider 缺失字段，保证旧 providers.json 向后兼容。"""
        for name, default_cfg in _DEFAULT_ASR_PROVIDERS.items():
            current = self._asr_providers.setdefault(name, copy.deepcopy(default_cfg))
            for key, value in default_cfg.items():
                current.setdefault(key, value)

    @staticmethod
    def _read_key(provider_cfg: dict):
        """读取 provider 对应的 .key 文件内容。文件不存在或为空返回 None。"""
        key_file = provider_cfg.get("key_file", "")
        if not key_file:
            return None
        key_path = os.path.join(_keys_dir(), key_file)
        if not os.path.exists(key_path):
            return None
        with open(key_path, "r", encoding="utf-8") as f:
            key = f.read().strip()
        return key or None


# ── 模块级单例 ────────────────────────────────────────────────────────────────

router = AIRouter()
