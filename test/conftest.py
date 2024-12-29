from __future__ import annotations

import asyncio
import os
import platform
import socket
import sys
from typing import Optional

import pytest
from mitmproxy.utils import data


# 通用的跳过标记，根据操作系统和网络条件选择性跳过测试
def check_ipv6_support() -> bool:
    """检查主机是否支持 IPv6"""
    try:
        with socket.socket(socket.AF_INET6, socket.SOCK_STREAM) as s:
            s.bind(("::1", 0))
        return True
    except OSError:
        return False


skip_windows = pytest.mark.skipif(os.name == "nt", reason="Skipping due to Windows")
skip_not_windows = pytest.mark.skipif(
    os.name != "nt", reason="Skipping due to not Windows"
)
skip_not_linux = pytest.mark.skipif(
    platform.system() != "Linux", reason="Skipping due to not Linux"
)
skip_no_ipv6 = pytest.mark.skipif(
    not check_ipv6_support(), reason="Host has no IPv6 support"
)


# 自定义事件循环策略，支持异步任务的优化
class EagerTaskCreationEventLoopPolicy(asyncio.DefaultEventLoopPolicy):
    """自定义事件循环策略，支持任务工厂配置"""

    def new_event_loop(self):
        loop = super().new_event_loop()
        if sys.version_info >= (3, 12):
            loop.set_task_factory(asyncio.eager_task_factory)
        return loop


@pytest.fixture(scope="session")
def event_loop_policy(request):
    """全局范围的事件循环策略"""
    return EagerTaskCreationEventLoopPolicy()


# 提供测试数据的工具
@pytest.fixture()
def tdata():
    """返回测试数据实例"""
    return data.Data(__name__)


# 异步日志捕获工具类
class AsyncLogCaptureFixture:
    """支持异步日志捕获的工具类"""

    def __init__(self, caplog: pytest.LogCaptureFixture):
        self.caplog = caplog

    def set_level(self, level: int | str, logger: Optional[str] = None) -> None:
        """设置日志捕获的日志级别"""
        self.caplog.set_level(level, logger)

    async def await_log(self, text: str, timeout: float = 2.0) -> bool:
        """等待日志中出现指定文本"""
        for _ in range(int(timeout / 0.01)):
            if text in self.caplog.text:
                return True
            await asyncio.sleep(0.01)
        raise AssertionError(f"Did not find {text!r} in log:\n{self.caplog.text}")

    def clear(self) -> None:
        """清空日志捕获内容"""
        self.caplog.clear()


@pytest.fixture
def caplog_async(caplog):
    """异步日志捕获的 pytest fixture"""
    return AsyncLogCaptureFixture(caplog)


# 新增的多功能网络检查工具
class NetworkUtils:
    """网络工具类，提供更多功能扩展"""

    @staticmethod
    def is_port_open(port: int) -> bool:
        """检查指定端口是否可以被绑定"""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False

    @staticmethod
    def get_local_ip() -> str:
        """获取本地机器的 IP 地址"""
        try:
            hostname = socket.gethostname()
            return socket.gethostbyname(hostname)
        except socket.error as e:
            return f"Error: {e}"


@pytest.fixture(scope="module")
def network_utils():
    """网络工具的 pytest fixture"""
    return NetworkUtils()


# 新增异步任务监控工具
class AsyncTaskMonitor:
    """监控异步任务的执行状态"""

    def __init__(self):
        self.tasks = []

    def add_task(self, coro: asyncio.coroutine):
        """添加协程任务到监控队列"""
        task = asyncio.create_task(coro)
        self.tasks.append(task)

    async def wait_for_all(self):
        """等待所有监控的任务完成"""
        await asyncio.gather(*self.tasks)

    def cancel_all(self):
        """取消所有监控的任务"""
        for task in self.tasks:
            task.cancel()

    async def ensure_all_complete(self):
        """确保所有任务完成，即使有被取消的"""
        try:
            await self.wait_for_all()
        except asyncio.CancelledError:
            pass


@pytest.fixture
def async_task_monitor():
    """异步任务监控的 pytest fixture"""
    return AsyncTaskMonitor()
