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
    """

    def set_busy(self, msg: str = "Running..."):
        """通知 Hub Tab 进入运行中状态（黄点）。"""
        if hasattr(self, "master") and hasattr(self.master, "set_status"):
            self.master.set_status("running")

    def set_done(self, msg: str = "Done"):
        """通知 Hub Tab 进入完成状态（绿点）。"""
        if hasattr(self, "master") and hasattr(self.master, "set_status"):
            self.master.set_status("done")

    def set_idle(self):
        """通知 Hub Tab 恢复空闲状态（灰点）。"""
        if hasattr(self, "master") and hasattr(self.master, "set_status"):
            self.master.set_status("idle")

    def log(self, msg: str):
        """写入统一日志。"""
        logger.info(msg)

    def log_error(self, msg: str):
        """写入错误日志。"""
        logger.error(msg)
