# services/metrics.py
import logging
import asyncio
import time
import json
from functools import wraps
from typing import Any, Callable, TypeVar, Dict

logger = logging.getLogger("app.metrics")

T = TypeVar('T')

def track_time(metric_name: str) -> Callable:
    """
    Performance timing decorator.
    Automatically handles both Async (await) and Synchronous functions.
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                start_time = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration = (time.perf_counter() - start_time) * 1000
                    metrics_collector.gauge(metric_name, duration)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args: Any, **kwargs: Any) -> T:
                start_time = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = (time.perf_counter() - start_time) * 1000
                    metrics_collector.gauge(metric_name, duration)
            return sync_wrapper
    return decorator

class StructuredLoggingMetricsCollector:
    """
    Production-ready metrics collector that emits structured JSON logs.
    This avoids the need for a dedicated StatsD sidecar in this deployment,
    while still allowing log aggregators (Splunk, ELK) to parse metrics.
    """
    def __init__(self):
        self.logger = logging.getLogger("metrics.collector")
        self.logger.info("✓ Structured Metrics Collector Initialized.")
    
    def increment(self, metric_name: str, tags: Dict[str, str] = None):
        """Log a counter increment."""
        payload = {
            "type": "COUNTER",
            "metric": metric_name,
            "value": 1,
            "tags": tags or {},
            "timestamp": time.time()
        }
        self.logger.info(json.dumps(payload))
        
    def gauge(self, metric_name: str, value: Any, tags: Dict[str, str] = None):
        """Log a gauge value (e.g., latency, memory)."""
        payload = {
            "type": "GAUGE",
            "metric": metric_name,
            "value": value,
            "tags": tags or {},
            "timestamp": time.time()
        }
        self.logger.info(json.dumps(payload))

# Global instance
metrics_collector = StructuredLoggingMetricsCollector()