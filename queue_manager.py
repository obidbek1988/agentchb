import asyncio
import time
import logging
from typing import Callable, Any
from config import REQUEST_DELAY_SECONDS

logger = logging.getLogger(__name__)

class SafeQueueManager:
    """
    Manages rate limits for Gemini API requests.
    Enforces a mandatory delay between API calls and processes tasks sequentially in queue.
    """
    def __init__(self, delay_between_requests: float = REQUEST_DELAY_SECONDS):
        self.delay = delay_between_requests
        self.last_call_time = 0.0
        self.queue = asyncio.Queue()
        self._lock = asyncio.Lock()
        self._worker_task = None

    async def execute_with_rate_limit(self, func: Callable, *args, **kwargs) -> Any:
        async with self._lock:
            now = time.time()
            elapsed = now - self.last_call_time
            if elapsed < self.delay:
                wait_time = self.delay - elapsed
                logger.info(f"Rate limiter: waiting {wait_time:.2f}s before calling Gemini...")
                await asyncio.sleep(wait_time)
            
            try:
                result = await func(*args, **kwargs)
                self.last_call_time = time.time()
                return result
            except Exception as e:
                self.last_call_time = time.time()
                raise e

queue_manager = SafeQueueManager()
