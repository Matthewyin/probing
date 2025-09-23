"""
进程管理器 - 统一管理所有子进程，确保资源正确清理
"""
import asyncio
import weakref
import signal
import time
from typing import List, Dict, Any, Optional, Set
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from .logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessInfo:
    """进程信息"""
    process: asyncio.subprocess.Process
    command: List[str]
    created_at: float = field(default_factory=time.time)
    timeout: Optional[float] = None
    description: str = ""


class ProcessManager:
    """
    统一的进程管理器
    
    功能：
    1. 跟踪所有活跃的子进程
    2. 提供统一的进程创建和清理接口
    3. 自动清理僵尸进程
    4. 监控进程资源使用
    """
    
    _instance: Optional['ProcessManager'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        self.active_processes: Dict[int, ProcessInfo] = {}
        self.cleanup_task: Optional[asyncio.Task] = None
        self._lock = None  # 延迟初始化
        self._cleanup_started = False
    
    def _ensure_initialized(self):
        """确保异步组件已初始化"""
        if self._lock is None:
            self._lock = asyncio.Lock()

        if not self._cleanup_started:
            self._cleanup_started = True
            try:
                self.cleanup_task = asyncio.create_task(self._periodic_cleanup())
            except RuntimeError:
                # 如果没有运行的事件循环，稍后再启动
                self._cleanup_started = False
    
    async def _periodic_cleanup(self):
        """定期清理僵尸进程"""
        while True:
            try:
                await asyncio.sleep(5)  # 每5秒检查一次，更频繁的清理
                await self._cleanup_finished_processes()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"Error in periodic cleanup: {e}")
    
    async def _cleanup_finished_processes(self):
        """清理已完成的进程"""
        self._ensure_initialized()
        async with self._lock:
            finished_pids = []
            
            for pid, info in self.active_processes.items():
                if info.process.returncode is not None:
                    finished_pids.append(pid)
            
            for pid in finished_pids:
                info = self.active_processes.pop(pid, None)
                if info:
                    logger.debug(f"Cleaned up finished process {pid}: {' '.join(info.command[:3])}")
    
    async def create_subprocess(
        self,
        *args,
        timeout: Optional[float] = None,
        description: str = "",
        **kwargs
    ) -> 'ManagedProcess':
        """
        创建受管理的子进程
        
        Args:
            *args: 传递给 asyncio.create_subprocess_exec 的参数
            timeout: 进程超时时间（秒）
            description: 进程描述
            **kwargs: 传递给 asyncio.create_subprocess_exec 的关键字参数
            
        Returns:
            ManagedProcess: 受管理的进程包装器
        """
        # 设置默认参数
        kwargs.setdefault('stdout', asyncio.subprocess.PIPE)
        kwargs.setdefault('stderr', asyncio.subprocess.PIPE)
        
        # 确保异步组件已初始化
        self._ensure_initialized()

        try:
            process = await asyncio.create_subprocess_exec(*args, **kwargs)

            # 注册进程
            async with self._lock:
                info = ProcessInfo(
                    process=process,
                    command=list(args),
                    timeout=timeout,
                    description=description
                )
                self.active_processes[process.pid] = info
            
            logger.debug(f"Created process {process.pid}: {description or ' '.join(args[:3])}")
            
            return ManagedProcess(process, self, timeout)
            
        except Exception as e:
            logger.error(f"Failed to create subprocess: {e}")
            raise
    
    async def kill_process(self, pid: int, force: bool = False):
        """
        终止指定进程
        
        Args:
            pid: 进程ID
            force: 是否强制终止（使用SIGKILL）
        """
        self._ensure_initialized()
        async with self._lock:
            info = self.active_processes.get(pid)
            if not info:
                return
            
            process = info.process
            if process.returncode is not None:
                return  # 进程已结束
            
            try:
                if force:
                    process.kill()
                else:
                    process.terminate()
                
                # 等待进程结束
                try:
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    if not force:
                        # 如果温和终止失败，强制终止
                        logger.warning(f"Process {pid} did not terminate gracefully, killing")
                        process.kill()
                        await asyncio.wait_for(process.wait(), timeout=5.0)
                
                logger.debug(f"Terminated process {pid}")
                
            except Exception as e:
                logger.warning(f"Error terminating process {pid}: {e}")
            finally:
                # 从活跃进程列表中移除
                self.active_processes.pop(pid, None)
    
    async def cleanup_all(self):
        """清理所有活跃进程"""
        self._ensure_initialized()
        async with self._lock:
            pids = list(self.active_processes.keys())
        
        for pid in pids:
            await self.kill_process(pid, force=True)
        
        # 取消清理任务
        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
    
    def get_process_count(self) -> int:
        """获取活跃进程数量"""
        return len(self.active_processes)
    
    def get_process_info(self) -> List[Dict[str, Any]]:
        """获取所有进程信息"""
        result = []
        for pid, info in self.active_processes.items():
            result.append({
                'pid': pid,
                'command': ' '.join(info.command[:3]) + ('...' if len(info.command) > 3 else ''),
                'description': info.description,
                'created_at': info.created_at,
                'running_time': time.time() - info.created_at,
                'timeout': info.timeout,
                'returncode': info.process.returncode
            })
        return result


class ManagedProcess:
    """
    受管理的进程包装器
    
    提供上下文管理器接口，确保进程资源正确清理
    """
    
    def __init__(self, process: asyncio.subprocess.Process, manager: ProcessManager, timeout: Optional[float] = None):
        self.process = process
        self.manager = manager
        self.timeout = timeout
        self._cleaned_up = False
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.cleanup()
    
    async def communicate(self, input_data: Optional[bytes] = None):
        """
        与进程通信，带超时处理

        Args:
            input_data: 发送给进程的输入数据

        Returns:
            (stdout, stderr): 进程输出
        """
        try:
            if self.timeout:
                result = await asyncio.wait_for(
                    self.process.communicate(input_data),
                    timeout=self.timeout
                )
            else:
                result = await self.process.communicate(input_data)

            # 进程完成后立即从管理器中移除
            if not self._cleaned_up:
                async with self.manager._lock:
                    self.manager.active_processes.pop(self.process.pid, None)
                self._cleaned_up = True

            return result
        except asyncio.TimeoutError:
            logger.warning(f"Process {self.process.pid} timed out")
            await self.kill()
            raise
    
    async def wait(self):
        """等待进程完成"""
        if self.timeout:
            return await asyncio.wait_for(self.process.wait(), timeout=self.timeout)
        else:
            return await self.process.wait()
    
    async def kill(self):
        """终止进程"""
        if not self._cleaned_up:
            await self.manager.kill_process(self.process.pid, force=True)
            self._cleaned_up = True
    
    async def terminate(self):
        """温和地终止进程"""
        if not self._cleaned_up:
            await self.manager.kill_process(self.process.pid, force=False)
            self._cleaned_up = True
    
    async def cleanup(self):
        """清理进程资源"""
        if not self._cleaned_up:
            if self.process.returncode is None:
                await self.terminate()
            else:
                # 进程已完成，直接从管理器中移除
                async with self.manager._lock:
                    self.manager.active_processes.pop(self.process.pid, None)
            self._cleaned_up = True
    
    @property
    def pid(self) -> int:
        """进程ID"""
        return self.process.pid
    
    @property
    def returncode(self) -> Optional[int]:
        """进程返回码"""
        return self.process.returncode


# 全局进程管理器实例
process_manager = ProcessManager()


@asynccontextmanager
async def managed_subprocess(*args, timeout: Optional[float] = None, description: str = "", **kwargs):
    """
    便捷的上下文管理器，用于创建受管理的子进程
    
    Usage:
        async with managed_subprocess('ping', '-c', '3', 'google.com', timeout=30) as proc:
            stdout, stderr = await proc.communicate()
            return proc.returncode
    """
    managed_proc = await process_manager.create_subprocess(
        *args, timeout=timeout, description=description, **kwargs
    )
    
    try:
        yield managed_proc
    finally:
        await managed_proc.cleanup()
