# AI Router tab 化 + core.ai 统一门面

## 目标

VideoCraft 目前所有 AI 能力（文本 LLM、ASR、TTS）散落在各个工具模块里各自调 SDK / API / Router，导致：
- Router 管理是独立 Toplevel 弹窗，与 Hub tab 范式不一致
- Router 只有单维度「档位」（低/中/高），无法表达"翻译用 A、字幕分段用 B、ASR 用 C"的差异化诉求
- UI 层直接 `import ai_router` / `from fish_audio_sdk import ...` / 直调 Lemonfox，换 provider 要到处改

本 draft 提出一揽子架构升级：
1. **Router 成为 Hub 内 tab**（"AI 控制台"），和其他工具一致
2. **所有 AI 调用统一走 `core/ai` 门面**，UI 层不再直接 import provider SDK
3. **Router 管理升级为「功能 × 档位」二维矩阵**，LLM / ASR / TTS 全统一

这是长期架构基础 — 所有重度依赖 AI 的功能（PPT2Video、字幕工作台、翻译等）都建立在这一层上。**实施优先级：高于 PPT2Video**。

---

## 现状盘点

### Router 与档位

- **Router 位置**：[src/router_manager.py](../../src/router_manager.py) 独立 `tk.Toplevel` + `grab_set` 弹窗（与 Hub tab 范式不一致）
- **档位结构**：[src/ai_router.py:30-80](../../src/ai_router.py#L30) `TIER_PREMIUM` / `TIER_STANDARD` / `TIER_ECONOMY`，单维度
- **Provider 池**：Gemini / DeepSeek / Custom（OpenAI 兼容）/ ClaudeCode，已删除 Groq

### AI 调用位点清单（call sites）

| 状态 | 位置 | 说明 |
|---|---|---|
| ✅ 已在 core | [core/srt_ops.py](../../src/core/srt_ops.py) generate_segments / refine / titles | 已走 router.complete，核心逻辑集中 |
| ⚠️ UI 层直调 Router | [translate_srt.py:411](../../src/tools/translate/translate_srt.py#L411) `router.complete_json(schema=_TRANSLATE_SCHEMA)` | 需迁入 core.ai |
| ⚠️ UI 层硬编码副本 | [srt_tools.py](../../src/tools/subtitle/srt_tools.py) 第 471 / 688 / 800 行 | 硬编码 prompt + router 调用，与 core/srt_ops.py 重复（与 L16 Prompt hub 重叠的技术债） |
| ⚠️ Router 按钮散落 | [translate_srt.py:334](../../src/tools/translate/translate_srt.py#L334)、[srt_tools.py:1180](../../src/tools/subtitle/srt_tools.py#L1180)、[text2video.py:56](../../src/tools/text2video/text2video.py#L56) | 每个工具都有"AI Router 管理"按钮弹旧 Toplevel，tab 化后改为激活/新建 router tab |

### ASR / TTS 位置（目前不走 Router，待纳入）

| 能力 | 位置 | Provider |
|---|---|---|
| ASR | [tools/speech/speech2text.py](../../src/tools/speech/speech2text.py) | Lemonfox / 本地 Whisper（直调，各自管 key） |
| TTS | [text2video.py:234](../../src/tools/text2video/text2video.py#L234) TTSApp | Fish Audio SDK（直调，`ai_router.get_tts_key("fish_audio")` 取 key） |

---

## 目标架构

### Router tab（"AI 控制台"）

替代旧 `router_manager.RouterManagerWindow` 弹窗，变成 Hub 内一个普通 tab（走 `_open_in_tab` 范式，和 SubtitleTool / SplitWorkbench 等一致）。

布局草图（详细 UI 待决策）：

```
┌─────────────────────────────────────────────────────┐
│  AI 控制台                                           │
├─────────────────────────────────────────────────────┤
│  ┌─ 功能 × 档位 矩阵 ──────────────────────────────┐ │
│  │              │ Premium │ Standard │ Economy    │ │
│  │  translate   │ Gemini  │ DeepSeek │ DeepSeek   │ │
│  │  subtitle.*  │ Gemini  │ Gemini   │ DeepSeek   │ │
│  │  asr         │ —       │ Lemonfox │ Whisper本地│ │
│  │  tts         │ —       │ FishAudio│ (Edge TTS?)│ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  ┌─ Provider / API Key 管理 ────────────────────────┐ │
│  │  Gemini      [key...] ✓ 可用                     │ │
│  │  DeepSeek    [key...] ✓ 可用                     │ │
│  │  Fish Audio  [key...] ✓ 可用                     │ │
│  │  Lemonfox    [key...] ⚠ 未配置                   │ │
│  │  ClaudeCode  (subprocess) ✓ 本地                 │ │
│  └──────────────────────────────────────────────────┘ │
│                                                       │
│  （可选）调用统计 / 费用估算 / 本月用量               │
└─────────────────────────────────────────────────────┘
```

### `core/ai` 统一门面

所有 AI 调用收拢到 `core/ai`（单文件还是目录待决策）。对外 API：

```python
from core import ai

# 文本 LLM
text = ai.complete(task="translate", prompt="...", tier=ai.Tier.STANDARD)
obj  = ai.complete_json(task="subtitle.refine", prompt="...", schema=...)

# 语音识别
srt = ai.asr(audio_path, task="asr.transcribe", language="en")

# 语音合成
mp3_bytes = ai.tts(text, task="tts.synthesize", voice="...", format="mp3")
```

关键设计点：
- **`task` 是命名空间化字符串**（`translate` / `subtitle.refine` / `asr.transcribe` / `tts.synthesize` / …），由 Router 内部映射到 `(provider, tier, model)`
- **`tier` 可选**：不传时用 Router 为该 task 配置的默认档位；传了就覆盖（调用方主动要求"这次用 premium"）
- **provider 细节完全被门面屏蔽**：调用方不知道也不关心底层是 Gemini 还是 DeepSeek，换 provider 只改 Router 配置不改 UI 代码

### UI 层规约

实施后强制：

```python
# ❌ 禁止
import ai_router
from fish_audio_sdk import Session
import requests  # 直接打 Lemonfox endpoint

# ✅ 唯一合法
from core import ai
```

这条规约通过 code review + 可选的 lint 规则（grep `import ai_router` / `from fish_audio_sdk` 出现在 `tools/` 下就报错）强制。

---

## 功能分类（task 命名空间）

初版建议：

| Task | 对应业务 | 当前调用方 |
|---|---|---|
| `translate.*` | SRT 翻译（JSON 结构化） | [translate_srt.py](../../src/tools/translate/translate_srt.py) |
| `subtitle.segments` | 生成分段描述 | [srt_ops.py](../../src/core/srt_ops.py) / [srt_tools.py](../../src/tools/subtitle/srt_tools.py) 副本 |
| `subtitle.refine` | 精炼分段 | 同上 |
| `subtitle.titles` | 生成标题 | 同上 |
| `asr.transcribe` | 音频 → SRT | [speech2text.py](../../src/tools/speech/speech2text.py) |
| `tts.synthesize` | 文本 → 音频 | [text2video.py](../../src/tools/text2video/text2video.py) TTSApp |

预留（未来扩展）：
- `prompt.*` — 给 BACKLOG L16「Prompt hub」预留
- `vision.*` — 图像理解（OCR / 描述）
- `embed.*` — 向量化

---

## 与 BACKLOG L16「Prompt 集中管理」的边界

两件事独立推进、不冲突：

| 议题 | 本 draft | L16 Prompt hub |
|---|---|---|
| 管什么 | **call sites**（哪里调 AI）+ **Router UI** | **prompt 字符串**（怎么存/编辑 prompt 内容） |
| 产出 | `core/ai` 门面 + Router tab | `prompts/` 目录 + 管理页 |
| 交汇 | `core.ai.complete(task=..., prompt_key=..., ...)` — 门面从 Prompt hub 取 prompt，调用方只传 key | 同左 |

可以先做本 draft（call sites 统一），prompt 仍硬编码在代码里；L16 后续完成时只需改 core.ai 内部从 prompt hub 加载，UI 不受影响。

---

## 待决策

### D-A：`core/ai` 代码组织

按能力拆分（推荐基调）vs 按 provider 拆分 vs 混合两层：

- **A1**：目录 + 按能力
  ```
  core/ai/__init__.py        # 对外门面：complete / complete_json / asr / tts
  core/ai/router.py          # task→provider 映射、Tier 枚举、配置持久化
  core/ai/llm.py             # complete / complete_json 实现（调 providers）
  core/ai/asr.py             # asr 实现
  core/ai/tts.py             # tts 实现
  core/ai/providers/gemini.py, deepseek.py, fishaudio.py, lemonfox.py, claudecode.py
  ```
- **A2**：单文件 `core/ai.py`（D8 全统一后 API 多，单文件会很长，不推荐）
- **A3**：只按 provider 拆（`core/ai/gemini.py` 等）— 缺能力维度的公共抽象

### D-B：Router tab 功能矩阵 UI

- 纯表格（Treeview / Grid）
- 每个功能一张卡片（卡片内三档位 provider 下拉）
- 折叠面板（按功能分组）

### D-C：调用统计是否纳入

展示各 provider 本月调用次数 / 估算费用 / 错误率？数据来源需要埋点。

### D-D：旧 `RouterManagerWindow` 去留

- 完全删除（目标：tab 化彻底）
- 保留为"高级设置"弹窗（低频维护场景）

### D-E：API key 存储统一化

目前 `keys/providers.json` 在软件目录（portable），Lemonfox / Fish Audio 各自可能有散落 key 位。新门面要求统一到 Router 管理，与 BACKLOG L17「用户数据绿色化」协同。

### D-F：长期 AI 架构议题（随讨论补充）

用户提到"涉及长期基于 AI 架构的开发问题"，本节作为占位符，后续讨论有结论再填入。

---

## 关联 BACKLOG 项

- 本 draft：[BACKLOG.md:15](../../BACKLOG.md#L15) 🔴 P1「AI Router Manager 改为 Hub 内 tab」— 将精简为一行指向本 draft
- 相关：[BACKLOG.md:16](../../BACKLOG.md#L16) 🔴 P1「Prompt 集中管理 + 用户自定义」— 边界如上
- 相关：[BACKLOG.md:17](../../BACKLOG.md#L17) 🔴 P1「用户数据绿色化」— API key 存储共同议题
- 下游：[BACKLOG.md:12](../../BACKLOG.md#L12) 🔴 P1「PPT 视频生成管线」— 重度依赖 core.ai 的 complete / tts / asr
- 参考：[docs/design/04-ai-router.md](../design/04-ai-router.md) — 当前 Router 的 shipped 设计文档
