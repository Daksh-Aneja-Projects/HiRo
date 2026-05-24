# /C:/HiRo Project/backend/gunicorn_conf.py - FIXED GUNICORN LOGGING DEADLOCK
import os
import sys
import logging
# CRITICAL FIX: Import settings here to ensure environment variables are loaded 
# early in the master process before any workers are forked.
from config.settings import settings

# CRITICAL FIX: Ensure PYTHONUNBUFFERED is set immediately in the environment 
# so subprocesses (workers) inherit it correctly.
os.environ['PYTHONUNBUFFERED'] = '1'

# CRITICAL FIX: Line-buffered I/O. Use a bare try/except in case reconfigure isn't available
try:
    if sys.stdout.isatty(): # Only attempt reconfigure if we're in an interactive-like terminal
        sys.stdout.reconfigure(line_buffering=True)
    if sys.stderr.isatty():
        sys.stderr.reconfigure(line_buffering=True)
except AttributeError:
    # This is safe; the PYTHONUNBUFFERED=1 handles the buffering fallback.
    pass 

def pre_load(server):
    """Master process startup - minimal logging only."""
    logger = logging.getLogger('gunicorn.error')
    logger.info("Gunicorn master starting - safe mode.")
    
def post_fork(server, worker):
    """Worker startup - safe logging config."""
    logger = logging.getLogger('gunicorn.error') 
    
    # Prevent logging deadlock 
    root_logger = logging.getLogger()
    
    # CRITICAL FIX: Set propagate to False before basicConfig to isolate gunicorn handler 
    # This prevents the root logger from sending logs up to the system/gunicorn root handler,
    # which can cause duplication/deadlock in a forked environment.
    root_logger.propagate = False
    
    # CRITICAL FIX: Use force=True to reconfigure logging in a forked process environment
    logging.basicConfig(
        level=logging.WARNING,  # Reduced noise
        format='%(asctime)s [%(levelname)s] %(process)d %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],  # STDOUT ONLY
        force=True
    )
    
    logger.info(f"Worker {worker.pid} ready - safe logging.")
    
    # CRITICAL FIX: Set propagate back to True after configuring the root logger, 
    # ensuring application loggers inherit properly.
    root_logger.propagate = True
    
def worker_abort(worker):
    """Worker SIGTERM - NO LOGGING (prevents deadlock)."""
    print(f"Worker {worker.pid} SIGTERM - clean exit", flush=True)

# GUNICORN CONFIG (SAFE)
bind = "0.0.0.0:8001"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
