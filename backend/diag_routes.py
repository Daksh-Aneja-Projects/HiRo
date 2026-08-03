# backend/diag_routes.py
# /C:/HiRo Project/backend/diag_routes.py
import importlib
import sys
import traceback
import os
from typing import Dict, Any, List, Optional

# Ensure backend path is in sys.path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def safe_import(name):
    try:
        m = importlib.import_module(name)
        return m, None
    except Exception:
        return None, traceback.format_exc()

print("=== SERVER IMPORT DIAGNOSTIC ===")

server, err = safe_import("server")

if server:
    print("? Server module imported successfully.")
    print("Server file:", getattr(server, "__file__", "<unknown>"))
    
    app = getattr(server, "app", None)
    if app:
        print(f"? FastAPI App found: {app.title}")
        print(f"Routes count: {len(app.routes)}")
        for r in app.routes:
            methods: Optional[List[str]] = getattr(r, "methods", None) 
            path = getattr(r, "path", getattr(r, "path_format", "<no-path>"))
            print(f" - {path} {methods}")
    else:
        print("? 'app' attribute not found in server module.")
else:
    print("? Server module failed to import.")
    print("Error:", err)
