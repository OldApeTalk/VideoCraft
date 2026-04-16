# AI Router tab 化 + core.ai 统一门面

## 目标

VideoCraft 目前所有 AI 能力（文本 LLM、ASR、TTS）散落在各个工具模块里各自调 SDK / API / Router。本 draft 提出一揽子架构升级，作为长期 AI 架构基础 — 所有重度依赖 AI 的功能（PPT2Video、字幕工作台、翻译等）都建立在这一层上。

**本 draft 的核心是三件事**：

1. **严格分层**：`UI → core/<feature> → core/ai`。UI 层不感知 AI 的存在
2. **统一门面**：`core.ai` 对所有 AI 能力（LLM + ASR + TTS）提供统一 API；UI 层绝不 `import core.ai`
3. **功能化配置**：Router 从"档位单维度"升级为「功能 × 档位」二维矩阵，作为 Hub 内 tab

**实施优先级**：高于 PPT2Video（PPT2Video 重度依赖 core.ai 就位）。

---

## 架构原则（5 条铁律）

这 5 条是本架构的**骨架**，任何实施必须满足：

### 原则 1：严格三层分层

```
┌─────────────────────────────────────────┐
│ UI Layer (tools/)                        │
│  - TranslateApp, PPT2VideoWorkbench...  │
│  - No AI awareness, no prompts visible  │
└──────────────┬──────────────────────────┘
               │ calls business APIs
               ▼
┌─────────────────────────────────────────┐
│ Core Business Layer (core/)              │
│  - translate.py, srt_ops.py, asr_ops.py │
│  - Handles chunking, progress, errors   │
└──────────────┬──────────────────────────┘
               │ calls AI infrastructure
               ▼
┌─────────────────────────────────────────┐
│ Core AI Infrastructure (core/ai/)        │
│  - LLM complete / complete_json         │
│  - ASR / TTS providers                  │
│  - Prompts (internal)                   │
│  - Router / tier mapping                │
│  - Capability introspection             │
└─────────────────────────────────────────┘
```

- UI 工具（TranslateApp 等）调用 `core.translate.translate_srt(...)` 等 feature API
- Feature 内部才 `from core import ai`
- **UI 禁止 `import core.ai`**（例外：Router tab 本身、未来 AI playground 这类"基础设施控制台"工具允许直接调）

### 原则 2：自描述接口

```python
capability = core.ai.describe(task="translate", tier="standard")
# {
#   "max_input_tokens": 128000,
#   "supports_json": True,
#   "supports_stream": True,
#   "supports_prefix_cache": True,
#   "supports_response_cache": True,    # 客户端可以做
#   "safe_concurrency": 1,              # Phase 1 统一 1
#   "latency_p50_ms": 3000,
#   "provider": "gemini",               # 实际路由到的 provider
#   "model": "gemini-2.5-flash",
# }
```

Feature 层用 capability 决定策略：整块发还是分批、是否启用流式、是否提示 prefix 缓存。UI 层只看最终进度和结果，不感知具体策略。

### 原则 3：ASR / TTS 对称封装

固定功能 API（ASR / TTS）和 LLM 共享门面结构：
- 调用 pattern 一致：`core.ai.xxx(input, task=..., ...)`
- Provider 差异藏在元数据（describe 返回）
- 无损切换 provider 靠 Router 配置，不改 feature 代码

### 原则 4：Prompt 对 UI 隐藏

- UI 工具层**禁止出现 prompt 字符串 / 编辑框**（现状 srt_tools.py 违反，需清理）
- Prompts 存储在 `prompts/*.md`（由 BACKLOG L16「Prompt 集中管理」管理）
- core.ai 按 `(task, provider, tier)` 二维索引加载 prompt — 不同 provider 可以配不同 prompt
- 唯一的 prompt 可视化入口：L16 提供的"Prompt 管理页"独立 tab，给高级用户 tune

### 原则 5：Prompt 驱动功能同理

subtitle.segments / refine / titles 等"表面看是业务功能、实际是 prompt 驱动"的 task，也全部归入此范式。UI 调 `core.srt_ops.generate_segments(srt, tier=...)`，完全不见 prompt 字符串。

---

## 现状盘点

### Router 与档位

- **Router 位置**：[src/router_manager.py](../../src/router_manager.py) 独立 `tk.Toplevel` + `grab_set` 弹窗
- **档位结构**：[src/ai_router.py:30-80](../../src/ai_router.py#L30) `TIER_PREMIUM` / `TIER_STANDARD` / `TIER_ECONOMY`，单维度
- **Provider 池**：Gemini / DeepSeek / Custom（OpenAI 兼容）/ ClaudeCode

### AI 调用位点清单

| 状态 | 位置 | 处置 |
|---|---|---|
| ✅ 已在 core | [core/srt_ops.py](../../src/core/srt_ops.py) | 修改为走 core.ai，Router 改功能分类 |
| ⚠️ UI 直调 Router | [translate_srt.py:411](../../src/tools/translate/translate_srt.py#L411) | 迁移到 `core/translate.py` |
| ⚠️ UI 层硬编码副本 | [srt_tools.py](../../src/tools/subtitle/srt_tools.py) 第 471/688/800 行 | 删除（与 core/srt_ops 重复） |
| ⚠️ Router 按钮散落 | [translate_srt.py:334](../../src/tools/translate/translate_srt.py#L334)、[srt_tools.py:1180](../../src/tools/subtitle/srt_tools.py#L1180)、[text2video.py:56](../../src/tools/text2video/text2video.py#L56) | 移除（Router tab 化后走 menu → AI → 控制台） |
| ⚠️ ASR 直调 | [tools/speech/speech2text.py](../../src/tools/speech/speech2text.py) Lemonfox/Whisper | 迁移到 `core/asr.py` → `core.ai.asr()` |
| ⚠️ TTS 直调 | [text2video.py:234](../../src/tools/text2video/text2video.py#L234) Fish Audio SDK | 迁移到 `core/tts.py` → `core.ai.tts()` |

---

## 目标架构

### core/ai 统一门面

对外 API（UI 不可见，feature 层调用）：

```python
from core import ai

# 文本 LLM
text = ai.complete(
    task="translate",           # 必填，命名空间化
    prompt_vars={...},          # 填入 prompt 模板的变量（prompt 字符串不出现在调用方）
    tier=ai.Tier.STANDARD,      # 可选，不传时用 Router 默认
    cancellation=token,         # 可选，X2 协作取消
    progress_cb=...,            # 可选，X5 流式留位
    cache_hint=None,            # 可选，X4 缓存留位（Phase 1 no-op）
    max_concurrency=1,          # X6 并发留位（Phase 1 固定 1）
)

obj = ai.complete_json(
    task="subtitle.refine",
    schema={...},
    prompt_vars={...},
    tier=ai.Tier.PREMIUM,
)

# 语音识别
srt_text = ai.asr(
    audio_path,
    task="asr.transcribe",
    language="en",
)

# 语音合成
mp3_bytes = ai.tts(
    text,
    task="tts.synthesize",
    voice="...",
    format="mp3",
)

# 能力查询
cap = ai.describe(task="translate", tier=ai.Tier.STANDARD)
```

### Router tab（AI 控制台）

替代旧 `RouterManagerWindow` 弹窗。Hub 内普通 tab，走 `_open_in_tab` 范式。

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
│  ┌─ 缓存 ───────────────────────────────────────────┐ │
│  │  当前缓存大小: N MB           [清空缓存]          │ │
│  │  （Phase 2 启用后才生效）                         │ │
│  └──────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### UI 层规约（强制约束）

实施后 `tools/` 下禁止出现：

```python
# ❌ 禁止
import ai_router
from fish_audio_sdk import Session
# 直接调 Lemonfox / Whisper API
```

唯一合法：

```python
# ✅
from core import translate, srt_ops, asr, tts  # business API
```

可选 lint 规则：grep `import ai_router` / `from fish_audio_sdk` / `import requests` 等出现在 `tools/` 下就报警。

### 功能分类（task 命名空间）

| Task | 对应业务 | Phase 1 是否实现 |
|---|---|---|
| `translate.*` | SRT 翻译（JSON 结构化） | ✅ |
| `subtitle.segments` | 生成分段描述 | ✅ |
| `subtitle.refine` | 精炼分段 | ✅ |
| `subtitle.titles` | 生成标题 | ✅ |
| `asr.transcribe` | 音频 → SRT | ✅ |
| `tts.synthesize` | 文本 → 音频 | ✅ |
| `prompt.*` | 给 L16 Prompt hub 预留 | ❌ 架构留位 |
| `vision.*` | 图像理解（OCR / 描述） | ❌ 架构留位 |
| `embed.*` | 向量化 | ❌ 架构留位 |

---

## 架构契约（X1~X6）

本节是 core.ai 门面的**行为契约**，实施时严格遵守。

### X1：错误处理契约

**9 种 AIError.Kind**（含 X2 的 CANCELLED）：

| Kind | 含义 | 可重试? | 谁重试 |
|---|---|---|---|
| NETWORK | DNS / TCP / TLS / timeout | ✅ | core.ai（3 次指数退避 1s/2s/4s）|
| AUTH | Key 无效 / 过期 / revoked | ❌ | — |
| QUOTA | 配额耗尽（日 / 月） | ❌ | — |
| RATE_LIMIT | 瞬时过频 | ✅ | core.ai（按 `Retry-After`，上限 60s）|
| REFUSED | 安全过滤拒绝 | ❌ | — |
| MALFORMED | JSON schema 不合格 | ⚠️ | feature 层决定 |
| OVERFLOW | 输入超 context window | ❌ | — |
| CANCELLED | 用户主动取消（X2）| ❌ | — |
| UNKNOWN | 未分类异常 | ❌ | — |

**AIError 结构**：

```python
class AIError(Exception):
    kind: Kind
    provider: str           # "gemini" / "deepseek" / "fish_audio" / ...
    message: str            # 面向用户的人话
    retry_after: float | None  # 秒
    raw: Exception | None   # 原始异常（供日志）
```

**三层重试分工**：
- **core.ai**：transport 类（NETWORK / RATE_LIMIT）
- **Feature 层**：semantic 类（MALFORMED 重写 prompt、OVERFLOW 自动降 tier / 分块）
- **UI 层**：user 类（提供"重试"按钮）

**UI 映射表**：

| Kind | UI 文案 | 推荐动作按钮 |
|---|---|---|
| NETWORK | "网络持续失败（已自动重试 3 次）" | 重试 / 取消 |
| AUTH | "API key 无效或过期" | **打开 AI 控制台** / 取消 |
| QUOTA | "{Provider} 配额已耗尽" | **切换 provider** / 取消 |
| RATE_LIMIT | "调用过频，请稍后重试" | 重试 / 取消 |
| REFUSED | "{Provider} 拒绝响应：{原因}" | 修改输入 / **换 provider** |
| MALFORMED | "AI 输出格式错误（已重试 N 次）" | 重试 / 调整 prompt |
| OVERFLOW | "输入过长（{N} tokens），建议降档或换 provider" | **打开 AI 控制台** / 取消 |
| CANCELLED | "已取消" | （无需按钮）|
| UNKNOWN | "未知错误：{详情}" + 展开查看 raw | 重试 / 取消 |

**落地工作量**：每个 provider 的原生异常 → AIError.Kind 映射表（一次性写好）。

### X2：取消传播

**协作式取消**（Python 没有安全的 thread interrupt 原语，只能协作）。

```python
class CancellationToken:
    _cancelled: bool = False
    _abort_cb: Callable | None = None
    
    def cancel(self):
        self._cancelled = True
        if self._abort_cb:
            self._abort_cb()   # 触发 HTTP 断流
    
    def throw_if_cancelled(self):
        if self._cancelled:
            raise AIError(kind=Kind.CANCELLED, ...)
```

**三层职责**：
- **UI**：点"取消"按钮 → 调 `token.cancel()` → 按钮立即变灰
- **Feature**：chunk 边界调 `token.throw_if_cancelled()`
- **core.ai Provider adapter**：HTTP 发起时 `token.register_abort(lambda: response.close())`

**取消语义**：**完全原子丢弃**，不保留半程产出。理由：translation 等 context-coupled task 的半程数据会造成后续质量割裂（模型失去前半段建立的术语/语气约定，重跑得到的风格不一致）。"独立批量任务"未来出现时再单独讨论恢复策略。

**响应时间承诺**：
- Provider 支持 HTTP abort：<1s
- 降级：等当前调用完成，最差 30s；UI 显示"正在等待当前调用结束..."
- 兜底：60s 超时硬限制

### X3：成本预估

**只显示 token 数，不做 $ 估算**。

```python
cap = ai.describe(task="translate", tier="standard")
# cap.max_input_tokens → feature 层算出会分 N 次
# UI 显示："预估 ~2500 tokens, ~20 次调用"
```

**不做 $ 估算的理由**（写入 draft 避免未来有人想加回来）：
- 无 provider 查价 API
- 爬 provider 官网脆弱且违反 ToS
- 内置价格表维护难过时
- Provider 分层定价 / 缓存折扣 / 批处理折扣让 $ 数字 ±30% 误差
- 用户自己最清楚自家账单（他们申请的 key）

**不做任何**：$ 存储、价格刷新、爬虫、用户自填单价字段。Router tab 也不展示 $。

### X4：缓存层（架构留位）

两种缓存机制识别清楚，Phase 1 都不实现。

| 机制 | 命中条件 | 生效场景 |
|---|---|---|
| A. Provider 前缀缓存 | 前缀相同（SRT 不变）、尾巴可变 | prompt 调优 |
| B. 客户端完全响应缓存 | 整个请求完全相同 | 重跑 / 重试 |

**API 留位**：

```python
# complete() 接受 cache_hint 参数
result = ai.complete(task="translate", prompt_vars={...}, cache_hint=None)

# describe() 返回字段
cap.supports_prefix_cache   # bool
cap.supports_response_cache # bool
```

Phase 1：`cache_hint` 参数存在但忽略。Phase 2 真痛时加 provider adapter 实现，API 不改。

**Phase 2 实施时的技术选择**（留笔记）：
- A 前缀缓存：Anthropic `cache_control` / Gemini Context Cache / DeepSeek 自动 / Fish Audio 不适用
- B 客户端缓存：`user_data/ai_cache/` 目录，SHA256 key，LRU + 7 天 TTL + 100MB 上限，temperature > 0.3 自动跳过

### X5：流式语义（架构留位）

**三条规约**（让未来加 token 级流式时不改 API）：

1. **callback 协议从第一天就用**。所有 feature 层 API 都接受 `progress_cb: Callable[[done, total], None]`，哪怕 Phase 1 只在最后调一次 `progress_cb(1, 1)`
2. **describe 含 `supports_stream: bool`** — Router 可以按 tier 选"支持流式的 provider"
3. **progress_cb 语义是"partial result ready"** — 不绑"chunk"这个词。未来若底层改成 token 流，feature 层把"凑齐一个 SRT 行"作为触发事件，协议不变，UI 不用改

Phase 1 只做 **chunk 级流式**（自然由能力查询驱动 — 长输入分块，每块完成触发 progress_cb）。

Token 级流式（打字机效果）Phase 1 不做，理由：VideoCraft 桌面工具不是 user-facing chat 服务，翻译 30s 用户等得起；token 级流式 JSON 解析复杂度显著上升，不划算。

### X6：并发模型（架构留位）

**Phase 1 全串行**。架构留三条线：

1. `describe()` 返回 `safe_concurrency: int`（provider 建议的并发数，Phase 1 统一返回 1）
2. Feature 层 API 签名含 `max_concurrency: int = 1`（Phase 1 调用方不传别的值）
3. Provider adapter 未来加 semaphore 做 rate limit；`AIError.Kind.RATE_LIMIT` 已在 X1 契约里，Phase 2 只需让 adapter 实现重试退让

**Phase 1 不做并发的理由**：
- VideoCraft 是桌面工具，翻译 30s 用户等得起
- Rate limit 管理复杂度（Gemini Free 10 RPM，一并发就可能触发）
- 已有实施复杂度够多（X1 契约、X2 取消、X5 回调协议），再加并发容易出岔

**Phase 2 实施时**：feature 层用 `concurrent.futures.ThreadPoolExecutor.submit + as_completed`，不引入 asyncio（和现有 Tkinter threading 模型同构）。

---

## Phase 1 vs Phase 2 施工单

这张表是**实施阶段的总纲**：

| 议题 | Phase 1 | Phase 2 留位（未来激活方式） |
|---|---|---|
| 三层分层 | ✅ 强制落地 | — |
| `core.ai` 门面 | ✅ complete / complete_json / asr / tts / describe | — |
| Router tab | ✅ 功能 × 档位矩阵 + provider 管理 | 加调用统计 / 错误率 |
| Task 命名空间 | ✅ translate / subtitle.* / asr / tts | 加 prompt.* / vision.* / embed.* |
| 错误契约 (X1) | ✅ 9 种 Kind + 三层重试 | — |
| 取消传播 (X2) | ✅ CancellationToken + HTTP abort | 独立批量任务的半程恢复 |
| 成本 (X3) | ✅ token 统计 | 永不做 $ 估算 |
| 缓存 (X4) | ❌ no-op（API 留位） | A 前缀缓存 + B 完全响应缓存 |
| 流式 (X5) | ❌ 只做 chunk 级 | Token 级 + partial SRT 行协议 |
| 并发 (X6) | ❌ 串行（`max_concurrency=1`） | ThreadPoolExecutor + 每 task 可配并发度 |
| Prompt 存储 | 暂用硬编码（与 L16 协同迁移） | L16 Prompt hub 完成后迁 prompts/*.md |
| API key 存储 | 当前 `keys/providers.json` | 与 L17「用户数据绿色化」协同迁 user_data/ |
| 旧 RouterManagerWindow | 删除 | — |
| 各 UI 工具里的 Router 按钮 | 删除（走菜单 → AI → 控制台） | — |
| 各 UI 工具里的 prompt 编辑框 | 删除（违反原则 4）| — |

---

## 与 BACKLOG L16「Prompt 集中管理」的边界

| 议题 | 本 draft | L16 Prompt hub |
|---|---|---|
| 管什么 | **call sites**（哪里调 AI）+ **Router UI**（task→provider 映射）| **prompt 字符串**（怎么存 / 编辑 prompt 内容）|
| 产出 | `core/ai` 门面 + Router tab | `prompts/` 目录 + 管理页 |
| 交汇 | `core.ai.complete(task="...", prompt_vars={...})` — 门面从 prompt hub 取 prompt 模板，feature 层只传 vars | 同左 |

两件事独立推进。本 draft 可以先做（call sites 统一），prompt 仍硬编码在 core.ai 模块里；L16 后续完成时只需改 core.ai 内部"从 prompt hub 加载"，UI 和 feature 层不受影响。

---

## 待决策

### D-A：`core/ai` 代码组织

推荐目录结构（D8 全统一后单文件太挤）：

```
core/ai/
  __init__.py        # 对外门面：complete / complete_json / asr / tts / describe / Tier / AIError / CancellationToken
  router.py          # task→provider 映射 + 配置持久化
  llm.py             # complete / complete_json 实现（调 providers）
  asr.py             # asr 实现
  tts.py             # tts 实现
  errors.py          # AIError + Kind 枚举
  cancellation.py    # CancellationToken
  providers/
    gemini.py
    deepseek.py
    fishaudio.py
    lemonfox.py
    claudecode.py
    openai_compat.py  # 给 Custom provider 复用
```

### D-B：Router tab 功能矩阵 UI

- 纯表格（Treeview / Grid）
- 每个功能一张卡片（卡片内三档位 provider 下拉）
- 折叠面板（按功能分组）

### D-C：旧 `RouterManagerWindow` 去留

决定：**完全删除**（tab 化后无必要保留）。

### D-D：API key 统一存储位置

目前 `keys/providers.json` 在软件根目录（portable）；ASR / TTS key 可能散落。统一迁到 `user_data/keys/`（与 BACKLOG L17「用户数据绿色化」协同）。

### D-E：`describe()` 的字段稳定性

API 签名未来演进策略 — 字段只加不改（backward-compatible），feature 层用 `cap.get("field", default)` 访问。

### D-F：长期架构议题

留位，后续讨论补充。

---

## 关联 BACKLOG 项

- 本 draft：[BACKLOG.md:15](../../BACKLOG.md#L15) 🔴 P1「AI Router tab 化 + core.ai 统一门面」
- 相关：[BACKLOG.md:16](../../BACKLOG.md#L16) 🔴 P1「Prompt 集中管理」— 边界如上
- 相关：[BACKLOG.md:17](../../BACKLOG.md#L17) 🔴 P1「用户数据绿色化」— API key 存储共同议题
- 下游：[BACKLOG.md:12](../../BACKLOG.md#L12) 🔴 P1「PPT 视频生成管线」— 依赖 core.ai 就位
- 参考：[docs/design/04-ai-router.md](../design/04-ai-router.md) — 当前 Router 的 shipped 设计文档
