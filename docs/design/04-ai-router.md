# AI Router 设计

VideoCraft 的统一 AI 路由层。所有需要调用大模型的工具都通过 `router` 单例，避免各模块分别管理 provider / key / 降级逻辑。

## 文件

- [src/ai_router.py](../../src/ai_router.py) — 核心路由，进程内单例 `router`
- [src/router_manager.py](../../src/router_manager.py) — 管理 UI（Provider & Key / 档位配置 / 调用统计）
- `keys/providers.json` — 持久化配置（首次运行自动生成；gitignored）
- `keys/*.key` — 独立存储的 API Key 文件（向后兼容）

## 档位

| 档位 | 常量 | 适用场景 |
|------|------|---------|
| 高档 | `TIER_PREMIUM` | 高精度推理、长文翻译 |
| 中档 | `TIER_STANDARD` | 常规翻译、字幕处理 |
| 低档 | `TIER_ECONOMY` | 高频批量、简单任务 |

每档独立配置 Provider + Model；未配置时按 `priority` 自动降级。

## Provider 类型

| 类型 | 内置条目 | 需要 API Key | 调用方式 |
|------|---------|------------|---------|
| `gemini` | Gemini | ✅ | `google.generativeai` SDK |
| `openai_compatible` | DeepSeek / Custom | ✅ | `openai` SDK + `base_url` |
| `claude_code` | ClaudeCode | ❌ | 本地 `claude -p` CLI subprocess |

**Groq 已于 2026-04 移除**，原因是实测 Llama / gpt-oss / qwen 系列在 VideoCraft 的翻译/分段任务上 NLP 质量不达标。未来如需接更多模型，计划通过中转式 router（OpenRouter / one-api）作为 `openai_compatible` 的 `base_url` 统一接入，而不是给每家单独建条目。老 `providers.json` 会在启动时自动清理残留的 Groq 条目和指向它的 tier_routing。

## 两种补全 API

### 纯文本：`complete()`

```python
from ai_router import router, TIER_STANDARD

text = router.complete(prompt, tier=TIER_STANDARD)
```

Provider 返回什么就给调用方什么（去首尾空白）。消费方自己决定怎么解析，历史上翻译/分段/标题生成都走这条。

### 结构化 JSON：`complete_json()`

```python
SCHEMA = {
    "type": "object",
    "properties": {
        "translations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "index": {"type": "integer"},
                    "text":  {"type": "string"},
                },
                "required": ["index", "text"],
            },
        },
    },
    "required": ["translations"],
}

result = router.complete_json(prompt, schema=SCHEMA, tier=TIER_STANDARD)
# → {"translations": [{"index": 1, "text": "你好"}, ...]}
```

Provider 被强制按 schema 返回 JSON，router 负责 parse。失败抛 `RuntimeError` 带原始输出片段。

各 provider 的 JSON 实现策略：

- **Gemini** — 原生 `generation_config.response_schema`，schema 用 OpenAPI-style dict 直接传入。
- **OpenAI 兼容** — `response_format={"type":"json_object"}`（DeepSeek 不支持 `json_schema` strict mode，只支持 object 模式）+ 把 schema JSON dump 到 system prompt 作为指令。
- **ClaudeCode** — `claude -p --output-format json` 返回信封 `{"type":"result","result":"..."}`，`result` 字段是模型原始输出，router 在 prompt 里要求模型返回 JSON 后再 `json.loads` 一次拆出内层。

所有 provider 的输出都经过 `_strip_json_fence` 兜底剥 markdown ```json ... ``` 代码围栏。

## ClaudeCode subprocess 设计要点

- **无 API Key**：依赖本机 `claude` CLI 自己的登录态，不读 `keys/*.key`。`_has_auth()` 辅助让 `claude_code` 类型跳过 key 文件检查。
- **默认关闭**（`enabled=False`）：用户必须在 Router Manager 显式勾选启用。
- **prompt 走 stdin**：避开 Windows 命令行 ~32KB 长度上限，支持长批次翻译 prompt。
- **`--permission-mode bypassPermissions`**：router 消费方只做纯文本/JSON 补全，不让模型用 Write/Edit，所以在本机跑安全。
- **`FileNotFoundError` 友好包装**：如果 `claude` 不在 PATH，抛出提示用户安装并配置完整路径的 `RuntimeError`，而不是 Python traceback。
- **自动回填**：`_normalize_providers()` 在启动时把 `_DEFAULT_PROVIDERS` 里的新增条目（如 ClaudeCode）写入老 `providers.json`，保证升级用户也能看到新 provider。

与参考 Web Chat 工程的区别：那边用 `claude-agent-sdk` + `can_use_tool` 回调实现浏览器 modal 审批 mutating 工具，需要 ProactorEventLoop 补丁、SSE、approval Future、文件路径 sandbox。**本地 app 场景下这些全都不需要** —— VideoCraft 只要 headless `claude -p` 同步补全。

## 消费方迁移现状

| 消费方 | API | 状态 |
|--------|-----|------|
| `tools/translate/translate_srt.py` | `complete_json` | ✅ 已迁移，用 `_TRANSLATE_SCHEMA` 约束 `{"translations":[{"index","text"}]}`，删除原 50 行 `【N】` 正则解析 |
| `core/srt_ops.py`（标题/分段/描述润色） | `complete` | 保留纯文本路径 |
| `tools/subtitle/srt_tools.py` | `complete` | 保留纯文本路径 |
| `tools/text2video/text2video.py` | `complete` | 保留纯文本路径 |

老 `complete()` API 不动，未迁移的消费方**零修改**继续工作。待翻译路径稳定运行一段时间后再决定是否把其他消费方跟进到 JSON 路径。

## 翻译 JSON 路径的容错

`translate_srt.py` 在 `complete_json` 失败或字幕数量不匹配时**按字幕行回退**：

- 整批次 JSON 调用失败 → 该批次所有字幕填充原文，继续下一批
- 部分 `index` 缺失 → 缺失位置填充原文
- 不抛异常到 UI，翻译任务不中断

原设计里的"模型乱加 markdown fence / 多余引号"等脆弱性问题在 JSON mode 下被 `_strip_json_fence` + 严格 schema 约束彻底消除。

## 管理 UI（`router_manager.py`）

三个标签页：

1. **Provider & Key** —— 列出所有 provider（含 ASR / TTS）状态与启用开关。Edit 弹窗按 `type` 条件渲染：
   - `gemini` / `openai_compatible` → API Key + （openai 额外）Base URL + 模型列表
   - `claude_code` → 可执行路径 + 超时 + 模型列表 + 灰色提示（"需先 `claude login`，无需 API Key"）。**不**显示 API Key 和 Base URL
2. **档位配置** —— 为 premium / standard / economy 三档分别选 Provider + Model 下拉
3. **调用统计** —— Treeview 显示 calls / errors / error_rate / last_used

## 历史

- **Phase 1（2026-03）** — 三档路由 + Gemini / Groq / DeepSeek / Custom 四 provider；消费方 SrtTools / Translate-srt-gemini 迁移
- **2026-04** — Groq 删除 + `complete_json` API + translate_srt 切 JSON schema + ClaudeCode subprocess provider 上线（Part A–F 六步实施，参见 commit 历史）
