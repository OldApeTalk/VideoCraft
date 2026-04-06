# 主界面 Hub 设计

## 文件：`src/VideoCraftHub.py`

---

## 窗口布局

```
┌─────────────────────────────────────────────────────────────────┐
│  File │ 下载 │ 语音转字幕 │ 翻译 │ 视频 │ 字幕 │ 文字转视频 │ AI │
├──────────────┬──────────────────────────────────────────────────┤
│ [🔄] 资源管理器 │ ● 音频提取 × │ ▶ TTS × │ ✓ 字幕烧录 ×          │
│──────────────│──────────────────────────────────────────────────┤
│ 📁 project  │                                                   │
│  🎬 video   │         当前激活工具的 UI                          │
│  📄 raw.srt │         (嵌入在右侧内容区，不弹出独立窗口)          │
│  📄 zh.srt  │                                                   │
│  🎵 audio   │                                                   │
├──────────────┴──────────────────────────────────────────────────┤
│ 日志面板（深色，4行，彩色级别标记）                               │
└─────────────────────────────────────────────────────────────────┘
```

- 左侧 Sidebar：宽 320px，`pack_propagate(False)`，可拖动分隔线调整
- 右侧内容区：Tab 栏 + 工具内容区（首次打开工具前显示欢迎页）
- 底部日志面板：高 90px，深色主题，`hub_logger` 统一接入

---

## Tab 系统设计

### 概述

工具窗口以 Tab 的形式嵌入右侧内容区，而非弹出 Toplevel 窗口。每个 Tab 对应一个工具实例，支持多个工具同时保持打开状态。

### Tab 状态颜色

| 状态 | 颜色 | 含义 |
|------|------|------|
| `idle`    | 灰 `#9e9e9e` | Tab 已打开，尚未执行任务 |
| `running` | 黄 `#ffc107` | 工具后台线程正在运行 |
| `done`    | 绿 `#4caf50` | 最近一次任务已完成 |

### 关键类：`ToolFrame(ttk.Frame)`

工具容器，作为 `master` 传给工具类的 `__init__`。静默拦截 Toplevel 专属调用，使工具类无需任何修改即可嵌入 Tab：

```python
class ToolFrame(ttk.Frame):
    def geometry(self, spec=None): return ""        # 忽略尺寸设置
    def title(self, string=None): ...               # 捕获标题 → Tab 标签
    def resizable(self, w=None, h=None): pass       # 忽略
    def set_status(self, status: str): ...          # 通知 Hub 更新圆点颜色
```

工具通过 `self.master.set_status("running")` / `"done"` 主动上报状态，使用 `getattr` guard 保持向下兼容（单独启动时为 no-op）：

```python
getattr(self.master, 'set_status', lambda _: None)("running")
threading.Thread(target=_work, daemon=True).start()
```

### 关键类：`TabBar(tk.Frame)`

自定义 Tab 栏（不使用 `ttk.Notebook`，以支持彩色圆点）：

```
TabBar (tk.Frame, height=34, bg=#e8e8e8)
 └─ tab_btn (tk.Frame, bg=#fff 激活 / #d0d0d0 非激活)
     ├─ dot    (tk.Label, text="●", fg=status_color)
     ├─ title  (tk.Label)
     └─ close  (tk.Label, text="×", hover=红色)
```

### Tab 生命周期

```
open_tool(key)
  └─ _open_in_tab(file_path, class_name, tool_key)
       ├─ 去重：已打开则 _select_tab(key) 直接切换
       ├─ 动态 import 工具模块（与原 Toplevel 方式相同）
       ├─ 创建 ToolFrame，注入 set_status 回调
       ├─ 实例化工具类（工具调用 master.title() → 捕获 Tab 标签）
       ├─ TabBar.add_tab(key, label, status="idle")
       └─ _show_tabs() + _select_tab(key)

关闭 Tab（× 按钮）
  └─ _close_tab(key)
       ├─ ToolFrame.destroy()
       ├─ TabBar.remove_tab(key)
       └─ 若无剩余 Tab → _show_welcome()
```

---

## Menu 结构

```
File
├── Open Folder...        对话框选择任意文件夹，自动生成 videocraft.json
├── Recent Projects ▶     子菜单，最多 10 条历史
└── Exit

下载
└── yt-dlp 下载器

语音转字幕
└── LemonFox API

翻译
└── Gemini 翻译

视频
├── 字幕烧录 / 逐字字幕 / 视频分段
├── 提取 MP3 / 调整音量 / 视频片段提取 / 自动分割 / 码率转换

字幕
├── 提取字幕文字 / 生成分段描述 / 提取段落内容 / 精炼分段 / 生成标题

文字转视频
├── ① 文字合成语音 / ② 生成字幕 SRT / ③ 合成视频
└── 每日要闻合成

AI
└── Router 管理

Help
└── 关于 VideoCraft
```

---

## TOOL_MAP 注册表

每条记录：`tool_key → {file, class}`

- `class: None` → subprocess 启动（当前无此类工具）
- `class: "ClassName"` → 嵌入 Tab（`_open_in_tab`）

当前注册 21 个工具，分布在 `VideoTools.py`、`SrtTools.py`、`text2Video.py`、`SubtitleTool.py`、`WordSubtitleTool.py`、`Speech2Text-lemonfoxAPI-Online.py`、`Translate-srt-gemini.py`、`SplitVideo0.2.py`、`yt-dlp-with simuheader ipv4.py`。

---

## Sidebar 行为

- `ttk.Treeview`，单层展示（不递归子文件夹）
- 右键菜单：按文件类型提供快捷操作（由 `operations.py` 的 `get_operations()` 驱动）
- 双击文件：`os.startfile(path)`（系统默认程序打开）
- 每 2 秒自动检测文件夹变化并刷新（`_schedule_auto_refresh`）

---

## 关键类结构

```python
class VideoCraftHub:
    # Tab 系统状态
    _tab_registry: dict[str, str]      # tool_key → tool_key（去重用）
    _tab_frames:   dict[str, ToolFrame] # tool_key → ToolFrame 实例
    _tab_bar:      TabBar
    _content_area: tk.Frame            # ToolFrame 的父容器
    _welcome_frame: tk.Frame           # 无 Tab 时的欢迎页

    # 核心方法
    open_tool(key, initial_file=None)  # 入口：打开或切换到工具 Tab
    _open_in_tab(...)                  # 动态 import → ToolFrame → Tab
    _select_tab(key)                   # 切换激活 Tab
    _close_tab(key)                    # 关闭 Tab，必要时恢复欢迎页
    _show_tabs()                       # 显示 Tab 栏 + 内容区
    _show_welcome()                    # 显示欢迎页

    open_folder(path=None)             # 打开项目文件夹
    refresh_sidebar()                  # 扫描文件夹更新 Treeview
```
