# /C:/HiRo Project/backend/utils/async_helpers.py
import asyncio
import logging
from typing import Callable, TypeVar, Any, Awaitable, Union 

logger = logging.getLogger(__name__)

T = TypeVar('T')

async def call_agent(func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    """
    Wraps a synchronous function call in asyncio.to_thread.
    """
    # CRITICAL FIX: Do not assume func is synchronous.
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    
    try:
        # Wrap synchronous blocking function in a thread
        return await asyncio.to_thread(func, *args, **kwargs)
        
    except Exception as e:
        logger.error(f"Async wrapper failed for {func.__name__}: {e}")
        # CRITICAL FIX: Reraise the exception so the caller can handle it  
        raise # Reraises the actual exception from the thread

# FIX: Renamed and fixed implementation of maybe_await
async def maybe_await(obj: Union[T, Awaitable[T]]) -> T:
    """
    Awaits a coroutine or returns the object directly if it is not awaitable.
    """
    if asyncio.iscoroutine(obj):
        return await obj
    return obj
