# 架构决策

## 单进程 + Toplevel 多窗口模式

**决策**：放弃 `subprocess.Popen` 启动工具，改为 `tk.Toplevel` 弹窗。

**保留 subprocess 的场景**：
- FFmpeg 调用（视频处理本就是子进程）

**保留 threading 的场景**：
- 所有长任务（AI 调用、下载、转写）

**好处**：
- AI Router 可作进程内单例，统计数据实时共享
- 无需 IPC、文件锁、守护进程
- 工具窗口关闭不影响主进程

---

## 工具双模式设计

每个工具文件同时支持两种运行方式：

```python
# 嵌入模式（被 Hub 调用）
win = tk.Toplevel(parent)
ToolClass(win)            # 传入 Toplevel 替代 Tk，接口兼容

# 独立模式（直接运行）
if __name__ == "__main__":
    root = tk.Tk()
    ToolClass(root)
    root.mainloop()
```

**兼容性**：`tk.Toplevel` 与 `tk.Tk` 共享 `title()`、`geometry()`、`destroy()` 等接口，工具类无需感知差异。

**注意**：若工具 `__init__` 内调用了 `self.root.mainloop()`，需移除（mainloop 由 Hub 统一管理）。

---

## 关键约束

- **不做全局状态共享**：工具间数据通过 Project 文件夹（文件系统）传递，不用共享内存
- **AI Router 是唯一进程内单例**：`from ai_router import router`
- **配置存储**：`keys/providers.json`（AI 配置），`~/.videocraft/recent.json`（最近工程）
