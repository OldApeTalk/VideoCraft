# VideoCraft 设计总览

## 项目定位

面向内容创作者的视频生产工具集，核心流程：
**YouTube 下载 → 语音转字幕 → 翻译 → 字幕烧录**

技术栈：Python + Tkinter GUI + FFmpeg + AI（Gemini / Groq / DeepSeek）

---

## 三阶段重构路线

### Phase 1：AI Router ✅ 已完成
统一 AI 调用层，支持多 Provider 按档位路由。
详见 [04-ai-router.md](04-ai-router.md)

### Phase 2：VS Code 风格主界面 ✅ 基础完成
将"按钮墙"式启动器重构为 Menu + Sidebar + Toplevel 工具窗口架构。
详见 [03-ui-hub.md](03-ui-hub.md)

### Phase 2.5：原子化重构 🚧 进行中
提取纯逻辑到 core 层，建立 Operation Registry，Sidebar 右键直接调用操作。
详见 [06-core-layer.md](06-core-layer.md)、[07-operations-registry.md](07-operations-registry.md)

### Phase 3：Pipeline 自动化（待规划）
在 Phase 2 的骨架上，实现跨工具的数据自动流转（下载→转字幕→翻译→烧录）。

---

## 核心设计原则

1. **Project = 文件夹**，任意文件夹均可打开，自动生成 `videocraft.json` 作为标识
2. **功能原子独立**，每个工具仍可单独运行（双模式：嵌入 Toplevel / 独立 Tk）
3. **单进程 + Toplevel**，工具以弹窗方式打开，共享 AI Router 统计和状态
4. **增量演进**，不做大爆炸重构，每步完成即可验证
5. **足够简单**，避免过度工程化

---

## 文件结构（目标态）

```
src/
├── VideoCraftHub.py         # Phase 2 新主入口（Menu + Sidebar）
├── VideoCraft.py            # 旧入口保留，不删除
├── project.py               # Project 模型（文件夹+JSON管理）
├── ai_router.py             # AI Router（Phase 1 完成）
├── router_manager.py        # Router 管理 UI
├── yt-dlp-with simuheader ipv4.py
├── Speech2Text-lemonfoxAPI-Online.py
├── Translate-srt-gemini.py
├── SubtitleTool.py
├── SrtTools.py
├── VideoTools.py
├── SplitVideo0.2.py
└── text2Video.py

keys/
├── providers.json           # AI Provider 配置 + 档位路由
└── *.key                    # 各 Provider API Key

docs/design/                 # 本设计文档
```

---

## 文档导航

| 文件 | 内容 |
|------|------|
| [01-architecture.md](01-architecture.md) | 架构决策与约束 |
| [02-project-model.md](02-project-model.md) | Project 模型与 JSON 版本策略 |
| [03-ui-hub.md](03-ui-hub.md) | 主界面 Hub 设计（Menu + Sidebar） |
| [04-ai-router.md](04-ai-router.md) | AI Router 设计（Phase 1） |
| [05-use-cases.md](05-use-cases.md) | 用例集 |
| [06-core-layer.md](06-core-layer.md) | core 层设计：逻辑/UI 分离 |
| [07-operations-registry.md](07-operations-registry.md) | Operation Registry：文件类型→右键操作映射 |
