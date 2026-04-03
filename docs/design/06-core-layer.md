# core 层设计：逻辑/UI 分离

## 设计动机

原有工具文件（VideoTools、SubtitleTool 等）将业务逻辑与 Tkinter UI 混在一起，
无法从 Sidebar 右键直接调用，也无法在不打开完整工具窗口的情况下执行操作。

## 目录结构

```
src/core/
├── __init__.py
├── srt_ops.py       ← SRT 字幕处理
├── video_ops.py     ← FFmpeg 视频/音频操作
└── subtitle_ops.py  ← 字幕烧录（待实现，成本最高）
```

## 设计原则

- **无 UI 依赖**：不 import tkinter，不调用 messagebox
- **返回结果，不弹窗**：成功返回路径字符串，失败 raise Exception
- **进度通过 callback**：`progress_callback: Callable[[str], None] = None`
- **输出路径可选**：默认在输入文件同目录自动命名

## 各模块 API

### `core/srt_ops.py`（已完成）

```python
def extract_text(srt_path, output_path=None, progress_callback=None) -> str
# 提取 SRT 纯文本 → .txt，返回输出路径

def get_stats(srt_path) -> dict
# {"count": int, "duration_sec": float, "has_chinese": bool}
```

### `core/video_ops.py`（已完成）

```python
def extract_mp3(video_path, output_path=None, bitrate="192k",
                progress_callback=None) -> str
# 提取 MP3，返回输出路径

def extract_clip(video_path, start, end, output_path=None,
                 progress_callback=None) -> str
# 快速切片（stream copy），start/end 格式 HH:MM:SS
```

### `core/subtitle_ops.py`（待实现）

```python
def burn_subtitles(video_path, srt_path, output_path=None,
                   style=None, progress_callback=None) -> str
# 字幕烧录，从 SubtitleTool.py 提取（UI 污染度高，分阶段重构）
```

## 现状分析

| 文件 | UI 污染度 | 提取状态 |
|------|-----------|---------|
| SrtTools.py | 0% | 可直接 import，无需提取 |
| SplitVideo0.2.py | 5% | 可轻量包装 |
| VideoTools.py | 20% | 已包装到 core/video_ops.py |
| SubtitleTool.py | 40% | 待重构，merge_videos/run_ffmpeg 深度耦合 UI |
