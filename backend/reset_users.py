# backend/reset_users.py
#!/usr/bin/env python3
"""Reset MongoDB users collection for FIVE TEST CREDENTIALS.
Run this after updating auth_service.py and server.py."""
import asyncio
import sys
import os
from pathlib import Path
from typing import Dict, Any
from datetime import datetime, timezone

# Add backend directory to path
backend_dir = Path(__file__).parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from motor.motor_asyncio import AsyncIOMotorClient
from config.settings import settings

async def reset_users():
    """Clear existing users and ensure five test credentials are seeded"""
    print("🔧 Resetting MongoDB users for FIVE TEST CREDENTIALS...")
    
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
        
        await auth_service.initialize_test_users() # This function now handles 5 users
        
        # Verify users were created
        users = await users_collection.find().to_list(length=10)
        print(f"\n✅ Created {len(users)} test users:")
        for user in users:
            portals = user.get('portals', [])
            print(f"   • {user['username']} - {user['role']}")
            print(f"     Access: {', '.join(portals)}")
        
        await mongo_client.close()
        
        print("\n🎉 Database reset complete!")
        print("📋 Available credentials:")
        print("   ┌──────────────────────────────────────────────────┐")
        print("   │ Username     │ Password │ Role         │ Access │")
        print("   ├──────────────────────────────────────────────────┤")
        print("   │ admin        │ admin    │ hrit_admin   │ ALL    │")
        print("   │ hrit_manager │ hrit_manager │ hrit_admin   │ ALL    │")
        print("   │ hrbp         │ hrbp     │ hrbp         │ MANAGER│")
        print("   │ manager      │ manager  │ manager      │ ESS+MSS│")
        print("   │ demo         │ demo     │ employee     │ ESS    │")
        print("   └──────────────────────────────────────────────────┘")
    
    except Exception as e:
        print(f"❌ Error resetting users: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(reset_users())