# 主界面 Hub 设计（Phase 2）

## 文件：`src/VideoCraftHub.py`

---

## 窗口布局

```
┌─────────────────────────────────────────────────────────────┐
│  File │ Download │ 语音转字幕 │ 翻译 │ 字幕 │ 视频 │ AI │ Help │
├────────────────┬────────────────────────────────────────────┤
│ [🔄 刷新]      │                                            │
│────────────────│         欢迎页 / 空白内容区                │
│ 📁 project名   │   （无 Project 时显示 Open Folder 提示）   │
│  🎬 video.mp4  │                                            │
│  📄 raw.srt    │                                            │
│  📄 zh.srt     │                                            │
│  🎵 audio.mp3  │                                            │
│                │                                            │
├────────────────┴────────────────────────────────────────────┤
│ 状态栏：D:\Videos\my_project                                │
└─────────────────────────────────────────────────────────────┘
```

Sidebar 宽度约 200px，可拖动分隔线调整。

---

## Menu 结构

```
File
├── Open Folder...        对话框选择任意文件夹，自动生成 videocraft.json
├── Recent Projects ▶     子菜单，最多显示 10 条历史
└── Exit

Download
└── yt-dlp 下载器

语音转字幕
└── LemonFox API

翻译
└── Gemini 翻译

字幕
├── 字幕烧录
├── SRT 工具
└── 视频分段

视频
├── 视频工具
└── 文字转视频

AI
└── Router 管理

Help
└── 关于 VideoCraft
```

---

## 工具启动方式

```python
TOOL_MAP = {
    "yt-dlp":        ("yt-dlp-with simuheader ipv4", "YouTubeDownloader"),
    "speech2text":   ("Speech2Text-lemonfoxAPI-Online", "SpeechToTextApp"),
    "translate":     ("Translate-srt-gemini", "TranslateApp"),
    "subtitle":      ("SubtitleTool", "SubtitleApp"),
    "srttools":      ("SrtTools", "SrtToolsApp"),
    "splitvideo":    ("SplitVideo0.2", "SplitVideoApp"),
    "videotools":    ("VideoTools", "VideoToolsApp"),
    "text2video":    ("text2Video", "Text2VideoApp"),
}

def open_tool(self, key):
    module_name, class_name = TOOL_MAP[key]
    mod = importlib.import_module(module_name)
    cls = getattr(mod, class_name)
    win = tk.Toplevel(self.root)
    cls(win)
    # 若工具支持 initialdir，预填 self.project.folder
```

---

## Sidebar 行为

- `ttk.Treeview`，单层展示（不递归子文件夹）
- 顶部刷新按钮手动刷新
- 双击文件：`os.startfile(path)`（系统默认程序打开）
- 无 Project 时显示提示文字，不显示文件树

---

## 关键类结构

```python
class VideoCraftHub:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.project: Project | None = None
        self._build_menu()
        self._build_layout()      # Sidebar + 内容区 + 状态栏

    def open_folder(self, path=None)   # 选择/打开文件夹
    def refresh_sidebar(self)          # 扫描文件夹更新 Treeview
    def open_tool(self, key)           # 以 Toplevel 启动工具
    def _update_statusbar(self)        # 显示当前工程路径
```
