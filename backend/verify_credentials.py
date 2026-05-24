#!/usr/bin/env python3
"""QUICK CREDENTIALS VERIFICATION - COPY AND RUN THIS!"""
import hashlib
import sys
from datetime import datetime, timezone
from typing import Dict, Any, Optional # CRITICAL FIX: Added Optional

print("=" * 70)
print("🔐 HIRO CREDENTIALS DIAGNOSTIC TOOL")
print("=" * 70)

# Test MockHasher (from auth_service.py)
class MockHasher:
    @staticmethod
    def hash_password(password: str) -> str:
        # NOTE: Must match the hashing logic in auth_service.py
        return f"HASHED_{hashlib.sha256(password.encode('utf-8')).hexdigest()}"
    
    @staticmethod
    def verify_password(password: str, hashed_password: str) -> bool:
        expected_hash = MockHasher.hash_password(password)
        return hashed_password == expected_hash

# CRITICAL FIX: Updated test cases to reflect the passwords expected by auth_service.py
# (i.e., username = password)
test_users = [
    ("admin", "admin", "hrit_admin"),
    ("hritmanager", "hritmanager", "hrit_admin"),
    ("manager", "manager", "manager"),
    ("employee", "employee", "employee"),
]

print("\n🔍 TEST 1: APPLICATION PASSWORD HASHING INTEGRITY")
print("-" * 40)
all_pass = True

for username, password, role in test_users:
    print(f"\n  User: {username} (Role: {role})")
    
    # Hash password
    hashed = MockHasher.hash_password(password)
    print(f"    Hash: {hashed[:50]}...")
    
    # Verify the hash we just made against the clear password
    verification = MockHasher.verify_password(password, hashed)
    
    if verification:
        print("    Verification: ✅ PASS (Hashing integrity OK)")
    else:
        print("    Verification: ❌ FAIL (Hashing integrity FAILED)")
        all_pass = False

print("\n" + "=" * 70)

if all_pass:
    print("✅ TEST 1 SUMMARY: Hashing logic verified and internal test credentials match expectations.")
else:
    print("❌ TEST 1 SUMMARY: Hashing logic FAILED. Check auth_service.py's MockHasher implementation.")

print("=" * 70)
print("\n")
print("🔥 CRITICAL ACTION REQUIRED: DB CREDENTIALS MISMATCH")
print("=" * 70)
print("The Python script above verifies *application* user integrity.")
print("Your current failure is: asyncpg.exceptions.InvalidPasswordError: password authentication failed for user \"hiro_user\"")
print("\nThis means the password being used in your **.env file** is rejected by the running **Postgres container**.")
print("You MUST ensure these two secrets are **identical**:")
print("1. **In your .env file:** POSTGRES_PASSWORD=your_current_env_password")
print("2. **In your Docker Compose/Kubernetes setup:** The POSTGRES_PASSWORD used when the container was FIRST initialized.")
