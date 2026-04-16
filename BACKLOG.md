# VideoCraft Backlog

> 开发计划看板。优先级：🔴 P1 必须修 / 🟡 P2 重要增强 / 🟢 P3 体验提升
> 状态：`[ ]` 待开始 / `[~]` 进行中 / `[x]` 已完成

---

## 第一批：基础可用性（先修再上线）

| 优先级 | 状态 | 功能 | 说明 |
|--------|------|------|------|
| 🔴 P1 | [ ] | PPT 视频生成管线 | Claude 对话产出 slide（md/html）→ PPT 插件渲染 → Claude 写备注讲稿 → TTS（Edge TTS 免费档 / Fish Audio 发布档）→ PPT 每页导出 PNG → ffmpeg 按音频时长拼接 + 字幕烧录 → MP4。完整管线草案见 [docs/draft/PPT2Videopipeline.md](docs/draft/PPT2Videopipeline.md) |
| 🟡 P2 | [ ] | extract-clip / auto-split 业务逻辑下沉到 core | [video_tools.py:127-193](src/tools/video/video_tools.py#L127-L193) 的 `get_keyframe_times / find_nearest_keyframe / auto_split_video(use_keyframes=...)` 仍在 UI 层自带 ffprobe/ffmpeg 实现，与 `core/video_split.split_one()` 能力重复。跟进项：切到统一 API，移除 UI 层的重复逻辑。菜单入口保留 |
| 🔴 P1 | [ ] | 字幕处理综合工作台 | 合并字幕菜单下 5 个独立窗口为一个工作台（对标 `split_workbench.py`），老入口保留平滑迁移。详见 [docs/draft/SubtitleWorkbench.md](docs/draft/SubtitleWorkbench.md) |
| 🔴 P1 | [ ] | AI Router tab 化 + core.ai 统一门面 | Router 独立弹窗改为 Hub tab，同时把所有 AI 调用（含 LLM/ASR/TTS）收拢到 `core/ai` 统一门面，UI 层不再直接 import provider SDK；Router 升级为「功能 × 档位」二维矩阵管理。是长期 AI 架构基础，优先级高于 PPT2Video 管线。详见 [docs/draft/AIRouterAndCoreAPI.md](docs/draft/AIRouterAndCoreAPI.md) |
| 🔴 P1 | [ ] | Prompt 集中管理 + 用户自定义 | 现状：翻译、分段、标题生成、分段精炼等 5+ 个硬编码 prompt 散落在 [translate_srt.py:304](src/tools/translate/translate_srt.py#L304)、[srt_ops.py:109](src/core/srt_ops.py#L109)、[srt_tools.py](src/tools/subtitle/srt_tools.py)（第 471/688/800 行及其重复副本），没有任何中央配置。需要：(a) 把所有 prompt 抽取到独立存储（建议 `prompts/*.md` 或 `prompts.json`）；(b) AI 菜单新增 Prompt 管理页，列出每个 prompt 的用途、占位符、默认内容；(c) 支持用户覆盖默认 prompt 保存为自定义版本；(d) 消费方从 prompt 库加载而不是硬编码字符串。同时解决 srt_tools.py 里 prompt 重复定义的技术债 |
| 🔴 P1 | [ ] | 用户数据绿色化 | 当前持久化位置混乱：portable 部分 `keys/providers.json`（[ai_router.py:154](src/ai_router.py#L154)）在软件目录；**非 portable** 部分在 `~/.videocraft/`：layout.json（[hub_layout.py:14](src/hub_layout.py#L14) 窗口几何）、settings.json（[i18n.py:18](src/i18n.py#L18) 语言）、recent.json（[project.py:132](src/project.py#L132) 最近项目）、presets/（[subtitle/presets.py:15](src/tools/subtitle/presets.py#L15) 烧录 preset）。对一个"解压即用"的 portable 软件来说全走 `~/.videocraft/` 不合理：换电脑 / U 盘迁移就丢配置。目标：统一迁到 `<软件根>/user_data/`（或类似），同时保留迁移逻辑把老的 `~/.videocraft/` 自动搬过去一次。实施前需评估：是否保留"单用户 / 单机器"的默认选项切换（用户可能确实想在多个 portable 副本间共享配置） |
| 🔴 P1 | [ ] | yt-dlp JS runtime 修复 | YouTube 下载时 yt-dlp 因缺少 JavaScript 运行环境抛兼容性警告，部分格式解析失败导致清晰度缺失或直接下载失败。修复方案：(a) 升级 yt-dlp 到最新版本；(b) portable 包内置或检测系统的 Node.js；(c) 调用时显式传 `--js-runtimes node`。涉及 [tools/download/yt_dlp_tool.py](src/tools/download/yt_dlp_tool.py) 参数组装与打包脚本 |

---

## 第二批：免费层功能补齐（增强竞争力）

| 优先级 | 状态 | 功能 | 说明 |
|--------|------|------|------|
| 🟡 P2 | [~] | 视频加水印 | 🟡 水印能力已在 subtitle_tool 烧录流程中实现（图片/文字/日期三种，位置透明度可配置）；待拆成独立工具或允许空字幕场景下使用 |
| 🟡 P2 | [ ] | SRT 时间轴整体偏移 | 字幕和视频对不上时，整体向前/向后偏移指定秒数 |
| 🟡 P2 | [ ] | SRT 格式转换 | SRT ↔ VTT / ASS，不同平台（B站/YouTube/剪映）格式要求不同（注：word_subtitle 可生成 ASS 卡拉OK效果，但非通用格式转换） |
| 🟡 P2 | [ ] | yt-dlp 下载时同步获取字幕 | yt-dlp 原生支持，加一个"同时下载字幕"选项，省去手动转录步骤 |
| 🟡 P2 | [ ] | 视频合并/拼接 | 多个视频片段按顺序合并为一个，自媒体剪辑常见需求 |

---

## 第三批：体验提升（用户留存）

| 优先级 | 状态 | 功能 | 说明 |
|--------|------|------|------|
| 🟢 P3 | [ ] | 分割视频前显示分段预览 | 执行前列出解析出的分段列表，让用户确认再运行 |
| 🟢 P3 | [ ] | 各工具窗口风格统一 | 大小、配色、按钮样式统一；目前各工具窗口风格不一 |
| 🟢 P3 | [~] | 输出路径可自定义 | 🟡 yt-dlp / speech2text / video_tools / subtitle_tool 已支持；仅 translate_srt 仍硬编码输出到源文件目录 |
| 🟢 P3 | [~] | 操作参数持久化 | 🟡 subtitle_tool 已完成 preset 系统（~/.videocraft/presets/subtitle_burn.json，支持命名保存/切换/记忆 last_used）；其他工具待跟进 |

---

## 已完成 ✅

| 完成时间 | 功能 | 备注 |
|---------|------|------|
| 2026-04 | 视频分割后端统一 + splitvideo 旧入口清理 | 新建 `core/video_split.py`：`SplitMode` 枚举（fast / keyframe_snap / accurate）+ `probe_keyframes()` 带 (path, mtime) 缓存 + `split_one()` 统一入口；`core/video_concat.split_segments()` 加 `mode` 参数（默认 `KEYFRAME_SNAP`）；综合工作台 UI 新增"分割模式"下拉 + 悬停 tooltip + 探测关键帧状态提示；删除 `tools/video/split_video.py` 整文件 + Hub TOOL_MAP / 菜单 / 右键 Operation 的 splitvideo 引用；i18n 同步 zh/en 双语（删 19 键 + 增 8 键，仍保持 875 对 875 对称）。`extract-clip` / `auto-split` 两入口按用户决策保留，跟进项已转为 P2 |
| 2026-04 | AI Router JSON 结构化 + Claude Code provider | 新增 `complete_json(schema=...)` API；translate_srt 切 JSON 路径；新增 ClaudeCode subprocess provider（本地 `claude -p` CLI，无需 key，默认关闭）；删除 Groq。详见 [docs/design/04-ai-router.md](docs/design/04-ai-router.md) |
| 2026-04 | 视频分割综合管理工作台 | `tools/video/split_workbench.py`：加载视频 + `subs.txt`，Treeview 列表 review + 增删改 + 就地编辑起始时间/标题；嵌入 VLC 播放器，单击跳转、双击播放；分段导出（stream copy）与跨段合并导出（重编码 + concat demuxer）。核心抽出到 `core/segment_model.py` 与 `core/video_concat.py`；VLC 封装在 `ui/vlc_player.py`，缺失时优雅降级。旧 `splitvideo` / `extract-clip` / `auto-split` 入口保留不动 |
| 2026-04 | 中英双语 i18n 全链路（Phase 1-7） | `tr()` + `src/i18n/{zh,en}.json` 806 keys；File > Preferences > Language 切换（重启生效）；工厂默认 English；覆盖 Hub + 全部工具 UI |
| 2026-04 | 统一错误提示 | 所有工具 `except` 捕获后显示真实报错，不再静默失败或只说"操作失败" |
| 2026-04 | text2video TTS 重构（Fish Audio） | Fish Audio 集成、单/多角色对话、SRT 生成（字符比例时轴）、多章节视频合成+字幕烧录、分割逻辑抽离 core 层；探索方向（音效叠加/AI排版/CLI驱动）保留为 parked 项 |
| 2026-04 | 字幕烧录工具 Preset 系统 | 27 项参数命名保存/切换；Default 受保护；last_used 记忆；~/.videocraft/presets/subtitle_burn.json |
| 2026-04 | 字幕烧录工具输出路径自定义 | 新增输出文件行（Entry+浏览+自动开关）；默认 `Video_<lang>.mp4` 同视频目录；auto_output 随 preset 持久化 |
| 2026-04 | YouTube 发布模块 | OAuth 2.0 登录；标题/描述/标签/可见性/播放列表 支持；Resumable Upload；定时发布（需保持应用运行） |
| 2026-04 | 语音转字幕界面异步化 | `_transcribe_audio` 改 threading；按钮转录中禁用；后台 after(0) 回写日志 |
| 2026-04 | yt-dlp 下载列表改 Checkbutton | 替换 Listbox 蓝色高亮；Canvas 滚动框架；默认全选；Select All/Deselect All 同步 |
| 2026-04 | 每日要闻合成模块（DailyNewsApp） | PIL像素级自动换行、ffmpeg滚屏叠加、9:16/16:9分辨率选择、字幕背景透明度、可编辑水印 |
| 2026-04 | Speech2Text verbose_json 模式 | 同时保存 .json + .srt；自动检测语言；文件名附ISO语言码；语言不匹配时 Hub 警告 |
| 2026-04 | 统一文件命名规范 | 下载文件：`{short}_{date}[_{quality}].{ext}`；SRT：`_{lang}.srt`；烧录后：`_sub_{lang}.mp4` |
| 2026-04 | yt-dlp 文件名截断优化 | 原标题 >20 字符显示为「前10…后10」，左侧资源栏可读 |
| 2026-04 | yt-dlp 传入 project folder | Hub 打开 yt-dlp 工具时自动填入当前项目目录 |
| 2026-04 | SubtitleTool 单语字幕烧录 | 仅选中一条轨道也可正常烧录；修复 output_path 赋值顺序 bug |
| 2026-04 | SRT 编码自动识别 | `read_srt()` 回退链：utf-8-sig → utf-8 → gbk → gb2312 → big5 → latin-1，全工具统一 |
| 2026-04 | Hub 全屏启动 + 侧边栏加宽 | 启动即 zoomed 全屏；侧边栏 200→320px |
| 2026-04 | ASR 默认语言改为英文 | 原为中文，大多数转录场景为英文内容 |
| 2026-04 | 媒体格式模块设计规范 | `docs/design/10-media-format-modules.md`；每种节目形态一个独立 class |
| 2026-04 | GitHub Actions CI/CD 打包发布 | tag 触发自动构建，生成 portable zip |
| 2026-04 | README 重写（中文，面向用户） | 三部分：介绍 / 安装 / 功能 |
| 2026-04 | 产品战略设计文档 | `docs/design/08-product-strategy.md` |
| 2026-04 | VideoCraftHub 主界面 | VS Code 风格，Toplevel 多窗口架构 |
| 2026-04 | AI Router 统一路由层 | 支持 Gemini / DeepSeek / Custom(OpenAI 兼容) / ClaudeCode 自动切换（Groq 已删除，ClaudeCode 默认关闭） |

---

## 探索方向（记录，暂不实现）

| 优先级 | 状态 | 功能 | 说明 |
|--------|------|------|------|
| 🟡 P2 | [ ] | 合成视频高级功能 | 音效叠加、多层视频叠加（类视频编辑工具），如背景音乐、B-roll 覆盖等 |
| 🟡 P2 | [ ] | AI 智能排版融合 | 将 AI 能力融入合成视频流程，如自动字幕排版、智能场景切换建议等 |
| 🟡 P2 | [ ] | CLI / AI 对话驱动视频合成 | 通过 AI 对话方式调用既有素材与工具合成视频，类 agent 驱动的视频生产线 |

---

## 需求池子（未评估，先记录）

| 需求 | 说明 |
|------|------|
| 全工程中文注释英文化 | 将所有 .py 文件中的中文注释统一改为英文，提升代码可读性与国际化 |
| 开发规范文档整理 | 代码风格、文档规则、命名规范等，待产品稳定后统一整理 |
| 字幕文件命名规则优化 | ASR/翻译产出的中英文 SRT 文件名存在可读性或冲突问题，需要重新梳理命名规则（哪些后缀表示哪种语言/阶段、与烧录输出如何区分） |
| ~~综合视频分割工作台~~ | 已提升至 P1「视频分割综合管理页」，见第一批 |
| Tab 工具面板可滚动布局 | 字幕烧录等工具 UI 内容越来越多，在较低分辨率或日志面板被拖大时底部控件会被挤出；需要给每个 Tab 的 ToolFrame 提供一个纵向可滚动容器（Canvas+Scrollbar 或类似），工具布局保持原生 grid 即可，由框架负责滚动 |
| i18n Phase 8：en.json 翻译质量打磨 | 当前 en.json 为"够用即可"水准（Phase 1-7 手工 + 机译混合），待有真实英文用户反馈后再统一 review 用词、语气、术语一致性 |

---

## 暂缓 / 不做

| 功能 | 原因 |
|------|------|
| 云化 / SaaS | 视频处理算力消耗大，并发/等待/成本三重问题 |
| Docker 分发 | 目标用户不具备 Docker 使用背景 |
| 跨平台（短期） | 先把 Windows 版做稳，Mac 需求出现时再考虑本地 Web 方案 |
| 批量处理 | 工作量大，先做单文件质量，后续再扩展 |
