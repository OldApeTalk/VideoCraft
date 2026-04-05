"""
hub_logger.py — 全局日志单例

工具使用方式：
    from hub_logger import logger
    logger.info("提取完成 → output.mp3")
    logger.warning("编码异常，已用 GBK 兜底读取")
    logger.error(f"处理失败: {e}")

Hub 启动时注册回调：
    logger.register_handler(callback)  # callback(level, msg, timestamp)
"""

import queue
import threading
from datetime import datetime


class HubLogger:
    """线程安全的全局日志单例。

    工具在任意线程调用 info/warning/error，消息会投入队列；
    Hub 注册 handler 后，消息由 Hub 通过 root.after() 在主线程消费并显示。
    若 Hub 尚未注册，消息暂存队列，等注册后立即回放。
    """

    def __init__(self):
        self._queue: queue.Queue = queue.Queue()
        self._handler = None          # callable(level, msg, ts) 或 None
        self._lock = threading.Lock()

    def register_handler(self, callback):
        """Hub 主线程启动时调用。

        callback 签名：callback(level: str, msg: str, ts: str)
        level 取值："info" / "warning" / "error"
        """
        with self._lock:
            self._handler = callback
        # 回放积压消息（Hub 注册前工具已发出的消息）
        while True:
            try:
                item = self._queue.get_nowait()
                callback(*item)
            except queue.Empty:
                break

    def _emit(self, level: str, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        with self._lock:
            handler = self._handler
        if handler:
            handler(level, msg, ts)
        else:
            self._queue.put((level, msg, ts))

    def info(self, msg: str):
        """操作成功、一般信息。"""
        self._emit("info", msg)

    def warning(self, msg: str):
        """非致命警告。"""
        self._emit("warning", msg)

    def error(self, msg: str):
        """操作失败，应包含真实异常信息。"""
        self._emit("error", msg)


# 模块级单例 — 所有工具 import 同一个实例
logger = HubLogger()
