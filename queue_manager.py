import asyncio
import time
import logging
from typing import Callable, Any, Tuple

from config import REQUEST_DELAY_SECONDS

logger = logging.getLogger(__name__)

class SmartQueueManager:
    def __init__(self, delay_seconds: float = 2.0):
        self.delay = delay_seconds
        self.last_call_time = 0.0
        self.active_requests = 0
        self._lock = asyncio.Lock()

    def get_queue_info(self) -> Tuple[int, int]:
        pos = self.active_requests + 1
        wait_seconds = pos * int(self.delay + 2)
        return pos, wait_seconds

    async def execute_task(self, func: Callable, *args, **kwargs) -> Any:
        self.active_requests += 1
        try:
            async with self._lock:
                now = time.time()
                elapsed = now - self.last_call_time
                if elapsed < self.delay:
                    wait_time = self.delay - elapsed
                    logger.info(f"Rate Limiter: waiting {wait_time:.2f}s...")
                    await asyncio.sleep(wait_time)

                # Execute in separate thread so it NEVER blocks the asyncio event loop!
                result = await asyncio.to_thread(func, *args, **kwargs)
                self.last_call_time = time.time()
                return result
        finally:
            self.active_requests = max(0, self.active_requests - 1)

queue_manager = SmartQueueManager(delay_seconds=REQUEST_DELAY_SECONDS)
