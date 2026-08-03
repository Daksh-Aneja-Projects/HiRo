# backend/reset_test_users.py
#!/usr/bin/env python3
"""Environment-aware user reset script for HiRo.
Reads test credentials from environment variables."""
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any

# Add backend directory to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings

async def reset_test_users():
    """Clear existing users and seed from environment variables"""
    print("🔧 Resetting MongoDB users with environment credentials...")
    
    try:
        # Connect to MongoDB
        mongo_client = AsyncIOMotorClient(settings.mongo_url())
        db = mongo_client[settings.MONGO_DB_NAME]
        users_collection = db["users"]
        
        # Delete all existing users
        result = await users_collection.delete_many({})
        print(f"✅ Deleted {result.deleted_count} existing users")
        
        # Import and run auth service initialization
        from services.auth_service import AuthService
        auth_service = AuthService(mongo_client)
        
        # and are only retrieved from environment/fallbacks inside auth_service.initialize_test_users().
        # We need the actual passwords for the print table summary.
        
        await auth_service.initialize_test_users()
        
        # Verify users were created
        users = await users_collection.find().to_list(length=10)
        print(f"\n✅ Created {len(users)} test users from environment:")
        
        # Get actual environment values (or defaults used by AuthService)
        env_users: list[tuple[str, str, str]] = [
            ("admin", getattr(settings, 'TEST_ADMIN_USERNAME', 'admin'), getattr(settings, 'TEST_ADMIN_ROLE', 'hrit_admin')),
            ("manager", getattr(settings, 'TEST_MANAGER_USERNAME', 'manager'), getattr(settings, 'TEST_MANAGER_ROLE', 'manager')),
            ("demo", getattr(settings, 'TEST_EMPLOYEE_USERNAME', 'demo'), getattr(settings, 'TEST_EMPLOYEE_ROLE', 'employee'))
        ]
        
        # Get passwords separately for the summary table (as they are secrets and not stored on the settings object, 
        # but the defaults are known for display in a test script).
        admin_pass = os.environ.get("TEST_ADMIN_PASSWORD", "admin")
        manager_pass = os.environ.get("TEST_MANAGER_PASSWORD", "manager")
        employee_pass = os.environ.get("TEST_EMPLOYEE_PASSWORD", "demo")
        
        
        for env_key, username, role in env_users:
            user = await auth_service.get_user_by_username(username)
            if user:
                portals = user.get('portals', [])
                print(f"   • {user['username']} - {user['role']}")
                print(f"     Access: {', '.join(portals)}")
            else:
                print(f"   ⚠️ {username} not found in database")
        
        await mongo_client.close()
        
        print("\n🎉 Database reset complete!")
        print("📋 Environment credentials loaded:")
        print("   ┌─────────────────────────────────────────────────┐")
        print("   │ Type     │ Username  │ Password │ Role         │")
        print("   ├─────────────────────────────────────────────────┤")
        print(f"   │ Admin    │ {getattr(settings, 'TEST_ADMIN_USERNAME', 'admin'):<9} │ {admin_pass:<8} │ hrit_admin   │")
        print(f"   │ Manager  │ {getattr(settings, 'TEST_MANAGER_USERNAME', 'manager'):<9} │ {manager_pass:<8} │ manager      │")
        print(f"   │ Employee │ {getattr(settings, 'TEST_EMPLOYEE_USERNAME', 'demo'):<9} │ {employee_pass:<8} │ employee     │")
        print("   └─────────────────────────────────────────────────┘")
    
    except Exception as e:
        print(f"❌ Error resetting users: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(reset_test_users())
