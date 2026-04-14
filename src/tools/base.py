"""
tools/base.py - ToolBase Mixin

所有工具 App 类的约定接口。继承此类可获得统一的状态回调快捷方法。
不重写 __init__，作为 Mixin 使用，不影响各工具的构造逻辑。

用法：
    class MyApp(ToolBase):
        def __init__(self, master, initial_file=None):
            self.master = master
            ...
            self.set_busy("正在处理...")
            ...
            self.set_done()
"""

import hub_logger

logger = hub_logger.logger


class ToolBase:
    """
    工具 App 基类 Mixin。
    要求子类在 __init__ 中设置 self.master（ToolFrame 实例）。
    All set_* methods below are thread-safe: they marshal the Tk widget
    mutation back onto the main thread via master.after(0, ...), so tools
    can freely call them from worker threads.
    """

    def _tab_status(self, status: str):
        """Thread-safe internal: flip the Hub tab dot to the given status."""
        if not (hasattr(self, "master") and hasattr(self.master, "set_status")):
            return
        try:
            self.master.after(0, self.master.set_status, status)
        except Exception:
            pass

    def set_busy(self, msg: str = "Running..."):
        """通知 Hub Tab 进入运行中状态（蓝点）。"""
        self._tab_status("running")

    def set_done(self, msg: str = "Done"):
        """通知 Hub Tab 进入完成状态（绿点）。"""
        self._tab_status("done")

    def set_idle(self):
        """通知 Hub Tab 恢复空闲状态（灰点）。"""
        self._tab_status("idle")

    def log(self, msg: str):
        """写入统一日志。"""
        logger.info(msg)

    def log_error(self, msg: str):
        """Write an error log line only. Use for secondary failures (cleanup,
        temp file removal) that should not flip the tab to red."""
        logger.error(msg)

    def set_error(self, msg: str):
        """Runtime failure: red log line + tab dot turns red.
        Use for main-path exceptions the user must notice. msg must include the
        real exception text."""
        logger.error(msg)
        self._tab_status("error")

    def set_warning(self, msg: str):
        """Non-fatal condition worth attention: orange log line + tab dot orange.
        Examples: overwriting existing output, quota nearing limit, fallback path."""
        logger.warning(msg)
        self._tab_status("warning")
