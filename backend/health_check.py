# /backend/health_check.py - FIXED (Credential Consistency)
#!/usr/bin/env python3
"""Health check script for Docker Compose environment.
Checks all services and credentials."""
import requests
import json
import sys
import time # CRITICAL FIX: Add missing import
from typing import Dict, Any, List
# CRITICAL FIX: Add missing import for `datetime` which is used in print statement in other files, 
# although not used here, for consistency if this script were part of the app environment.
from datetime import datetime, timezone 


def check_service(url: str, name: str, timeout: int = 5) -> Dict[str, Any]:
    """Check if a service is responding"""
    try:
        response = requests.get(url, timeout=timeout)
        return {
            "service": name,
            "url": url,
            "status": "healthy" if response.status_code == 200 else "unhealthy",
            "status_code": response.status_code
        }
    except Exception as e:
        return {
            "service": name,
            "url": url,
            "status": "unreachable",
            "error": str(e)
        }

def test_login(base_url: str, username: str, password: str) -> Dict[str, Any]:
    """Test login with credentials"""
    try:
        response = requests.post(
            f"{base_url}/api/auth/login",
            data={"username": username, "password": password}, 
            headers={"Content-Type": "application/x-www-form-urlencoded"}, # CRITICAL FIX: Specify header
            timeout=5
        )
        response.raise_for_status()
        data = response.json()
        
        # FIX: Ensure user data is extracted correctly
        user_data = data.get('user', {})

        return {
            "status": "success",
            "role": user_data.get('role', 'N/A'),
            "token": data.get('access_token', 'N/A')[:10] + "...",
            "user_id": user_data.get('user_id', 'N/A'),
        }
    except requests.exceptions.HTTPError as e:
        detail = e.response.json().get('detail', 'Authentication failed')
        return {"status": "failure", "detail": detail, "error": str(e)}
    except Exception as e:
        return {"status": "error", "error": str(e)}

def main():
    base_url = os.environ.get("BACKEND_URL", "http://localhost:8001")
    
    print("=" * 50)
    print("🚀 HIRO END-TO-END HEALTH CHECK")
    print(f"Base URL: {base_url}")
    print("=" * 50)

    # 1. Service Checks
    print("\n🌐 Service Connectivity:")
    
    services_to_check = [
        (f"{base_url}/api", "FastAPI Core"),
        (f"{base_url}/health", "FastAPI Health"),
        ("http://postgres_db:5432/health", "PostgreSQL (Internal)"), # NOTE: This should typically fail in CI unless network is configured
        ("http://nats:4222", "NATS JetStream (Internal)"),
    ]
    
    for url, name in services_to_check:
        result = check_service(url, name)
        status_icon = "✅" if result["status"] == "healthy" else ("⚠️" if result["status"] == "unhealthy" else "❌")
        print(f"   {status_icon} {name}: {result['status'].upper()} ({url})")
    
    # 2. Detailed API Health Check
    print("\n🔬 API Internal Health Check:")
    detailed_health = check_service(f"{base_url}/api/health/detailed", "Detailed Health")
    if detailed_health['status_code'] == 200 and 'services' in detailed_health:
        health_data = detailed_health
    else:
        health_data = {"services": {}}
        print("   ❌ Detailed check failed. Skipping internal service list.")

    for service_name, result in health_data['services'].items():
        if isinstance(result, dict) and 'status' in result:
            status_icon = "✅" if result["status"] == "healthy" else ("⚠️" if "warning" in result["status"] else "❌")
            print(f"   {status_icon} {service_name.upper()}: {result['status']}")

    # 3. Test credentials
    print("\n🔐 Test Credentials Verification:")
    # CRITICAL FIX: ADDED HRBP AND HRIT_MANAGER
    credentials = [
        ("admin", "admin"),
        ("hrit_manager", "hrit_manager"), # Added hrit_manager
        ("hrbp", "hrbp"), 
        ("manager", "manager"),
        ("demo", "demo"),
    ]
    
    for username, password in credentials:
        result = test_login(base_url, username, password)
        status_icon = "✅" if result["status"] == "success" else "❌"
        print(f"   {status_icon} {username}/{password}: {result['status'].upper()}")
        
        if result["status"] == "success":
            print(f"      Role: {result['role']}")
            print(f"      Token: {result['token']}")
        elif "detail" in result:
            print(f"      Detail: {result['detail']}")
        elif "error" in result:
            print(f"      Error: {result['error']}")
    
    # Summary
    print("\n" + "=" * 50)
    print("🎉 Health Check Complete! (If Postgres/NATS show 'unreachable', they are not in the current shell's network.)")
    print("\n📋 Quick Access:")
    print(f"   Frontend: http://localhost:3000")
    print(f"   Backend API: {base_url}/api")
    print(f"   API Docs: {base_url}/api/docs")

if __name__ == "__main__":
    import os
    if not os.environ.get("BACKEND_URL"):
        print("Warning: BACKEND_URL not set in environment. Defaulting to http://localhost:8001")
    main()
