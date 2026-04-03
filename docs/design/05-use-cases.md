# 用例集

## UC-01：下载 YouTube 视频并建立工程

**触发**：用户拿到一个 YouTube 链接，需要处理。

**交互流程**：
1. 打开 VideoCraftHub
2. `File > Open Folder...` → 选择或新建目标文件夹（如 `D:\Videos\my_project\`）
3. Hub 打开该文件夹：
   - 自动生成 `videocraft.json`（若不存在）
   - Sidebar 显示文件夹内容（初始为空）
   - 状态栏显示当前工程路径
4. `Download > yt-dlp 下载器` → 弹出下载工具 Toplevel
   - 初始目录预填为当前工程文件夹
   - 用户粘贴 URL，点击下载
5. 下载完成 → 视频文件出现在工程文件夹
6. 点击 Sidebar 刷新按钮 → `🎬 video.mp4` 出现在列表

---

## UC-02：翻译已有 SRT 文件

**触发**：用户已有一份英文 SRT，需要翻译为中文。

**交互流程**：
1. `File > Open Folder...` → 选择含 SRT 的文件夹
2. Sidebar 显示 `📄 english.srt`
3. `翻译 > Gemini 翻译` → 弹出翻译工具 Toplevel
   - 源文件选择框预填工程文件夹路径（用户仍需点选具体文件）
4. 翻译完成 → `📄 english_zh.srt` 出现在 Sidebar

---

## UC-03：重新打开上次的工程

**触发**：用户关闭程序后重新打开，想继续上次的工作。

**交互流程**：
1. 打开 VideoCraftHub
2. `File > Recent Projects` → 子菜单显示最近 10 个工程
3. 点击目标工程路径 → 直接打开该文件夹
4. Sidebar 恢复显示上次的文件列表

---

## UC-04：管理 AI Provider 配置

**触发**：用户需要更换 AI 模型或添加新的 API Key。

**交互流程**：
1. `AI > Router 管理` → 弹出 Router 管理 Toplevel
2. 在 `Provider & Key` Tab 编辑 API Key
3. 在 `档位配置` Tab 为各档位选择 Provider + Model
4. 保存后生效，所有工具的下次 AI 调用即使用新配置

---

## UC-05：独立运行单个工具（开发/调试模式）

**触发**：开发者需要单独测试某个工具。

```bash
python src/SrtTools.py
python src/router_manager.py
python src/Translate-srt-gemini.py
```

每个工具的 `__main__` 块直接启动独立 Tk 窗口，无需 Hub。
