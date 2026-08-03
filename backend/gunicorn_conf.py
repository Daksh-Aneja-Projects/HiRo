# Gunicorn configuration for the HiRo backend.
import os
import sys
import logging
# Import settings in the master process so environment variables are loaded
# before any workers are forked.
from config.settings import settings

# Set in the master process so forked workers inherit unbuffered I/O.
os.environ['PYTHONUNBUFFERED'] = '1'

# Line-buffered I/O; reconfigure() is unavailable on some streams, hence the guard.
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
    
    root_logger = logging.getLogger()

    # Detach the root logger from gunicorn's handler while reconfiguring, so logs
    # are not duplicated up to the gunicorn root handler in a forked worker.
    root_logger.propagate = False

    # force=True replaces any handlers inherited across the fork.
    logging.basicConfig(
        level=logging.WARNING,
        format='%(asctime)s [%(levelname)s] %(process)d %(name)s: %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )

    logger.info(f"Worker {worker.pid} ready - safe logging.")

    # Re-enable propagation so application loggers inherit the root configuration.
    root_logger.propagate = True
    
def worker_abort(worker):
    """Worker SIGTERM - NO LOGGING (prevents deadlock)."""
    print(f"Worker {worker.pid} SIGTERM - clean exit", flush=True)

# GUNICORN CONFIG (SAFE)
bind = "0.0.0.0:8001"
workers = 2
worker_class = "uvicorn.workers.UvicornWorker"
timeout = 120
