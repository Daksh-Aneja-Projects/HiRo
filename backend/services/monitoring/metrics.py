"""Application Metrics Collection"""
import time
import math
from typing import Callable, Any, Dict, List
from functools import wraps
import inspect

class MetricsCollector:
    def __init__(self):
        self.function_times: Dict[str, List[float]] = {}
        self.function_counts: Dict[str, int] = {}

    def record_time(self, function_name: str, duration_ms: float):
        self.function_times.setdefault(function_name, []).append(duration_ms)
        self.function_counts[function_name] = self.function_counts.get(function_name, 0) + 1

    def get_metrics(self) -> Dict[str, Any]:
        metrics = {}
        for name, times in self.function_times.items():
            if times:
                metrics[f"{name}_count"] = self.function_counts.get(name, 0)
                metrics[f"{name}_avg_ms"] = round(sum(times) / len(times), 2)
                
                n = len(times)
                if n >= 1:
                    sorted_times = sorted(times)
                    index = min(n - 1, int(math.ceil(0.95 * n)) - 1)
                    metrics[f"{name}_p95_ms"] = round(sorted_times[index], 2)
        
        metrics["service_status"] = "operational"
        return metrics

metrics_collector = MetricsCollector()

def track_time(function_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.perf_counter()
                try:
                    return await func(*args, **kwargs)
                finally:
                    duration = (time.perf_counter() - start_time) * 1000
                    metrics_collector.record_time(function_name, duration)
            return wrapper
        else:
            @wraps(func)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                start_time = time.perf_counter()
                try:
                    return func(*args, **kwargs)
                finally:
                    duration = (time.perf_counter() - start_time) * 1000
                    metrics_collector.record_time(function_name, duration)
            return wrapper
    return decorator