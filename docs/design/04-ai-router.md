# AI Router 设计（Phase 1 — 已完成）

## 文件

- `src/ai_router.py` — 核心路由逻辑，进程内单例
- `src/router_manager.py` — 管理 UI（可独立运行）

---

## 核心概念

### 三档路由

| 档位 | 常量 | 适用场景 |
|------|------|---------|
| 高档 | `TIER_PREMIUM` | 高精度推理、长文翻译 |
| 中档 | `TIER_STANDARD` | 常规翻译、字幕处理 |
| 低档 | `TIER_ECONOMY` | 高频批量、简单任务 |

每个档位可独立配置 Provider + Model，通过 Router 管理 UI 设置。

### Provider 支持

- Gemini（Google）
- Groq
- DeepSeek（OpenAI-compatible）
- Custom（任意 OpenAI-compatible 端点）

---

## API

```python
from ai_router import router, TIER_PREMIUM, TIER_STANDARD, TIER_ECONOMY

# 按档位调用（推荐）
result = router.complete(prompt, tier=TIER_STANDARD)

# 显式指定 Provider + Model
result = router.complete(prompt, provider="Gemini", model="gemini-2.5-flash")

# 读/写档位配置
routing = router.get_tier_routing()
router.set_tier_routing(tier, provider, model)

# Provider 操作
router.get_provider_names()
router.get_provider_models("Gemini")
router.set_provider_enabled("Groq", False)
router.update_provider("Custom", base_url="...", models=["model-a"])

# 调用统计
stats = router.get_stats()
# {"Gemini": {"calls": 10, "errors": 0, "last_used": "..."}, ...}
```

---

## 配置存储

`keys/providers.json`（首次运行自动生成）：
```json
{
  "tier_routing": {
    "premium":  {"provider": "Gemini",  "model": "gemini-2.5-pro"},
    "standard": {"provider": "Gemini",  "model": "gemini-2.5-flash"},
    "economy":  {"provider": "Groq",    "model": "llama-3.3-70b"}
  },
  "providers": {
    "Gemini":  {"type": "gemini",  "key_file": "Gemini.key",  "enabled": true},
    "Groq":    {"type": "openai_compatible", "key_file": "Groq.key", "enabled": true},
    "DeepSeek":{"type": "openai_compatible", "key_file": "DeepSeek.key", "enabled": true}
  }
}
```

API Key 单独存储在 `keys/*.key` 文件（向后兼容旧版）。

---

## 已迁移模块

- `SrtTools.py` — `ai_generate()` 委托给 router
- `Translate-srt-gemini.py` — UI 改为档位选择 + Router 管理按钮

## 未迁移（暂不需要）

- `Speech2Text-lemonfoxAPI-Online.py`（LemonFox 非通用 AI 接口）
- `Translate-srt.py`（DeepL/Azure，非 LLM 调用）
