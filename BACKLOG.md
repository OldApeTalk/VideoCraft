# VideoCraft Backlog

> 开发计划看板。优先级：🔴 P1 必须修 / 🟡 P2 重要增强 / 🟢 P3 体验提升
> 状态：`[ ]` 待开始 / `[~]` 进行中 / `[x]` 已完成

---

## 第一批：基础可用性（先修再上线）

_本批次已清空，完成的条目见下方「已完成」。_

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
| 2026-04 | AI Router JSON 结构化 + Claude Code provider | 分 6 个 Part 完成：(A) 删除 Groq（实测 NLP 质量不达标，未来通过中转 router 接入更多模型）；(B) `ai_router.complete_json(prompt, schema=..., tier=...)` 新 API，Gemini 走 `response_schema`、OpenAI 兼容走 `response_format={"type":"json_object"}` + system prompt 注入 schema、`_strip_json_fence` 兜底；(C) `translate_srt.py` 切 JSON schema，删掉 50 行 `【N】` 正则解析，改按 `{"translations":[{"index":int,"text":str}]}` 回填，缺失位置用原文兜底；(D) ClaudeCode subprocess provider（`claude_code` 类型，默认 `enabled=False`，无 key_file，同时实现 `complete()` + `complete_json()`，走 `claude -p --output-format text/json`，prompt 走 stdin 避开 Windows cmdline 长度上限，`FileNotFoundError` 包装为友好提示，`_has_auth()` 辅助跳过 key 检查，`_normalize_providers()` 向后兼容旧 providers.json 自动回填新 provider）；(E) Router Manager Edit 弹窗按 type 分发，新增 `_build_claude_code_dialog`（可执行路径+超时+模型列表+提示，无 API Key/Base URL）；(F) i18n 新增 `label_executable` / `label_timeout_sec` / `claudecode_hint` 三键（zh+en）。老 `complete()` 路径保持不变，未迁移的消费方（srt_ops / srt_tools 的标题/分段/描述）继续走纯文本；Groq 老 providers.json 自动迁移清理 |
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
