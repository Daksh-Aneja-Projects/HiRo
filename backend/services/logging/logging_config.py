def _make_consumer_handlers():
    """Construct consumer handlers."""
    handlers = []
        
    # Stream handler
    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(FORMATTER)
    handlers.append(stream)

    # File handler (optional)
    if LOG_FILE:
        try:
            # CRITICAL FIX: Ensure logs directory exists
            log_path = Path(LOG_FILE)
            
            # If path is not absolute, make it relative to /app
            if not log_path.is_absolute():
                log_path = Path("/app") / log_path
            
            # Create parent directory if it doesn't exist
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_h = RotatingFileHandler(str(log_path), maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT)
            file_h.setFormatter(FORMATTER)
            handlers.append(file_h)
            print(f"✅ File logging configured: {log_path}", file=sys.stderr)
        except Exception as e:
            print(f"⚠️ Failed to setup file logging: {e}", file=sys.stderr)
            print(f"⚠️ LOG_FILE was: {LOG_FILE}", file=sys.stderr)
            
    return handlers