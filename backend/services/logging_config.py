"""Production-safe logging for HiRo."""
from __future__ import annotations
import logging
import logging.handlers
import sys
import os
from queue import SimpleQueue
from logging.handlers import QueueHandler, QueueListener, RotatingFileHandler
from typing import Optional
from pathlib import Path 

# Configuration
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.environ.get("LOG_FILE", "app.log") 
LOG_MAX_BYTES = int(os.environ.get("LOG_MAX_BYTES", 10 * 1024 * 1024))
LOG_BACKUP_COUNT = int(os.environ.get("LOG_BACKUP_COUNT", 5))
USE_QUEUE_LOGGING = True

# Globals
_queue_listener: Optional[QueueListener] = None
_queue: Optional[SimpleQueue] = None

# Logging format
FORMATTER = logging.Formatter(
    # Added process ID and thread ID for debugging multi-process/multi-threaded scenarios
    "%(asctime)s %(levelname)-8s [%(name)s:%(lineno)d] (PID:%(process)d|TID:%(thread)d) %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def _make_consumer_handlers():
    """Construct consumer handlers (these run in the separate listener thread)."""
    handlers = []
        
    # Stream handler (Writes to STDOUT, often managed by the container/Gunicorn)
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(FORMATTER)
    handlers.append(stream)

    # File handler (optional)
    if LOG_FILE:
        try:
            # Ensure logs directory exists relative to CWD if not absolute path
            log_path = Path(LOG_FILE)
            if not log_path.is_absolute():
                 # Default to 'logs/app.log' if a simple filename is given
                 log_path = Path("logs") / LOG_FILE 
                 log_path.parent.mkdir(parents=True, exist_ok=True)
            elif log_path.is_absolute() and not log_path.parent.exists():
                 # If absolute path and parent doesn't exist, skip file handler setup
                 raise RuntimeError("Log file parent directory does not exist.")

            file_h = RotatingFileHandler(
                str(log_path), 
                maxBytes=LOG_MAX_BYTES, 
                backupCount=LOG_BACKUP_COUNT,
                encoding='utf-8' # Good practice to specify encoding
            )
            file_h.setFormatter(FORMATTER)
            handlers.append(file_h)
        except Exception as e:
            # Print to stderr since the main logging system might not be fully operational yet
            print(f"Failed to setup file logging: {e}", file=sys.stderr)
            
    return handlers

def init_logging():
    """Initialize queue-based logging."""
    global _queue_listener, _queue
    
    # Already initialized
    if _queue_listener is not None:
        return
        
    # 1. Create the Queue and Handler
    _queue = SimpleQueue()
    queue_handler = QueueHandler(_queue)
        
    root = logging.getLogger()
        
    # Remove existing handlers (important for multiprocess start/stop)
    for h in list(root.handlers):
        try:
            root.removeHandler(h)
        except Exception:
            pass
            
    # 2. Configure the Root Logger
    root.setLevel(LOG_LEVEL)
    root.addHandler(queue_handler)
    
    # 3. Configure Consumer Handlers
    consumer_handlers = _make_consumer_handlers()
    
    # CRITICAL FIX: Patch consumer handlers to prevent re-entrant errors. 
    # This prevents the handler writing to stderr/file from trying to log its own failure.
    for h in consumer_handlers:
        h.handleError = lambda record: None

    # 4. Start the Listener Thread
    # The QueueListener picks up records from the queue and passes them to the consumer handlers
    _queue_listener = QueueListener(_queue, *consumer_handlers, respect_handler_level=True)
    _queue_listener.start()
        
def get_logger(name: str) -> logging.Logger:
    """Convenience function to initialize logging if necessary and return a logger instance."""
    if _queue_listener is None:
        init_logging()
    return logging.getLogger(name)

def shutdown_logging():
    """Stop the QueueListener thread."""
    global _queue_listener
    if _queue_listener:
        _queue_listener.stop()
        _queue_listener = None
