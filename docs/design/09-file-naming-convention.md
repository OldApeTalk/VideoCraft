# 09 — 文件自动命名规则

## 设计动机

VideoCraft 各工具输出文件命名风格不一致，同目录下难以识别处理阶段和语言。
统一命名规则解决以下问题：
- 同一视频的下载版、字幕版、烧录版混在一起无法区分
- 多语言 SRT 文件无法一眼识别语言
- 长标题文件名在侧边栏资源管理器中截断导致不可读

---

## 核心约定

### 语言标签
统一使用 **ISO 639-1 小写双字母码**：`en` `zh` `ar` `fr` `ru` `es` `ja` `ko`……  
自动检测：`auto`  
粤语等无标准双字母码的：使用三字母码 `yue`

### 后缀语义

| 模式 | 含义 | 示例 |
|------|------|------|
| `_{lang}.srt` | 转录/识别，单语言 | `video_en.srt` |
| `_{src}-{tgt}.srt` | 翻译，src→tgt | `video_en-zh.srt` |
| `_sub_{langs}.mp4` | 字幕已烧录 | `video_sub_zh+en.mp4` |
| `_{quality}.mp4` | 非最优画质下载 | `video_720p.mp4` |

### 标题截断规则（下载场景）
YouTube 标题往往超过 60 字符，严重影响侧边栏可读性。

**规则：** 超过 20 字符时，保留 `前10字符 + … + 后10字符`

```
Tucker Carlson Tonight Full Episode January 15 2024
→ Tucker Car…ary 15 2024
```

不足 20 字符时保留完整标题。

---

## 各工具命名规则

### 1. yt-dlp 下载器

**格式：** `{短标题}_{日期}[_{画质}].{ext}`

| 情况 | 文件名 |
|------|--------|
| 最优画质（best/1080p） | `Tucker Car…ary 15 2024_20240115.mp4` |
| 指定 720p | `Tucker Car…ary 15 2024_20240115_720p.mp4` |
| 提取 MP3 | `Tucker Car…ary 15 2024_20240115.mp3` |

实现：下载完成后通过 `os.rename()` 重命名（yt-dlp 模板不支持两端截断）。

### 2. 语音转字幕（Speech2Text）

**格式：** `{源文件名}_{lang}.srt`，语言用 ISO 码

| 语言选择 | 输出文件名 |
|---------|-----------|
| Auto Detect | `video_auto.srt` |
| English | `video_en.srt` |
| Chinese | `video_zh.srt` |
| Haitian Creole | `video_ht.srt` |

从 `language_dict` 的 key（即 ISO 码）直接反查，无需字符串处理。

### 3. 字幕翻译（Translate）

**格式：** `{源文件名}_{src}-{tgt}.srt`

连字符 `-` 区分翻译方向，与转录的单语 `_{lang}` 语义不同。

| 操作 | 输出文件名 |
|------|-----------|
| en → zh 翻译 | `video_en-zh.srt` |
| auto → en 翻译 | `video_auto-en.srt` |

### 4. 字幕烧录（SubtitleTool）

**格式：** `{源视频名}_sub_{langs}.mp4`

从 SRT 文件名末尾推断语言标签（`_en` → `en`），推断失败时回退为 `sub`。

| 字幕配置 | 输出文件名 |
|---------|-----------|
| 仅中文字幕（video_zh.srt） | `video_sub_zh.mp4` |
| 仅英文字幕（video_en.srt） | `video_sub_en.mp4` |
| 中英双语 | `video_sub_zh+en.mp4` |
| 无法推断语言 | `video_sub.mp4` |

---

## 辅助函数（实现参考）

```python
def _short_title(title: str, max_len: int = 20, head: int = 10, tail: int = 10) -> str:
    """超过 max_len 时截为 前head字符…后tail字符。"""
    if len(title) <= max_len:
        return title
    return title[:head] + "…" + title[-tail:]


def _infer_lang_tag(srt_path: str) -> str:
    """从 SRT 文件名推断语言码，回退为 'sub'。
    video_en.srt → 'en'
    video_en-zh.srt → 'en-zh'（翻译文件）
    """
    base = os.path.splitext(os.path.basename(srt_path))[0]
    parts = base.rsplit("_", 1)
    if len(parts) == 2 and len(parts[1]) <= 5:
        return parts[1]
    return "sub"
```
