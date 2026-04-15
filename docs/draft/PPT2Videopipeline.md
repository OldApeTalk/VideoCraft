# PPT视频生成管线

```mermaid
flowchart TD
    A["💬 Claude对话\n主题 / 大纲 / 内容"]
    B["📄 生成Slide文件\nMarkdown / HTML结构"]
    C["📊 PPT插件 + Claude\n渲染为PowerPoint"]
    D["✍️ Claude写备注讲稿\n按页分段"]
    E{"TTS选择"}
    F["🆓 Edge TTS\n免费 · 日常用途"]
    G["🎙️ Fish Audio API\n高音质 · 对外发布"]
    H["🎵 每页音频文件\n时长自动计算"]
    I["🖼️ PPT导出图片\n每页一张"]
    J["🎬 Python + ffmpeg\n音画拼接 · 字幕生成"]
    K["📹 输出MP4视频\n自动翻页 · 音画同步"]

    A --> B
    B --> C
    C --> D
    D --> E
    E -->|"普通场景"| F
    E -->|"重要发布"| G
    F --> H
    G --> H
    C --> I
    H --> J
    I --> J
    J --> K
```

## 各节点说明

| 节点 | 工具 | 备注 |
|------|------|------|
| Claude对话 | Claude.ai 网页版 | 生成内容大纲和Slide结构 |
| 生成Slide | Markdown / HTML | 结构化内容，便于插件解析 |
| PPT插件 + Claude | Claude for PowerPoint | 渲染成正式PPT文件 |
| 写备注讲稿 | Claude | 按页分段，控制每段时长 |
| Edge TTS | edge-tts Python库 | 免费，无需API key |
| Fish Audio API | Fish Audio | 高音质，适合对外发布 |
| PPT导出图片 | python-pptx | 每页导出为PNG |
| 音画拼接 | ffmpeg | 按音频时长控制每页停留时间 |
| 输出MP4 | ffmpeg | 含字幕，音画自动同步 |
