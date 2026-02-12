#!/usr/bin/env python3
"""
Test script to verify database setup
Run this before starting the main application
"""

import sys
import os

# Add backend to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def main():
    print("=" * 60)
    print("🔧 PAROT DATABASE SETUP TEST")
    print("=" * 60)
    
    # Step 1: Check environment variables
    print("\n1. Checking environment variables...")
    from dotenv import load_dotenv
    load_dotenv()
    
    db_name = os.getenv('DB_NAME')
    db_user = os.getenv('DB_USER')
    db_host = os.getenv('DB_HOST', 'localhost')
    db_port = os.getenv('DB_PORT', '5432')
    
    if not db_name or not db_user:
        print("❌ ERROR: Database credentials not found in .env file!")
        print("   Please create a .env file with:")
        print("   - DB_NAME=your_database_name")
        print("   - DB_USER=your_username")
        print("   - DB_PASSWORD=your_password")
        return False
    
    print(f"   ✅ DB_NAME: {db_name}")
    print(f"   ✅ DB_USER: {db_user}")
    print(f"   ✅ DB_HOST: {db_host}")
    print(f"   ✅ DB_PORT: {db_port}")
    
    # Step 2: Test database connection
    print("\n2. Testing database connection...")
    try:
        from database import test_connection
        if not test_connection():
            print("❌ Database connection failed!")
            print("   Please check:")
            print("   - PostgreSQL is running")
            print("   - Database exists")
            print("   - Credentials are correct")
            return False
    except Exception as e:
        print(f"❌ Error testing connection: {e}")
        return False
    
    # Step 3: Import models
    print("\n3. Importing database models...")
    try:
        from database import models
        print("   ✅ Models imported successfully")
        print(f"   - Found {len(models.Base.metadata.tables)} table definitions:")
        for table_name in models.Base.metadata.tables.keys():
            print(f"     • {table_name}")
    except Exception as e:
        print(f"❌ Error importing models: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 4: Create tables
    print("\n4. Creating database tables...")
    try:
        from database import init_db
        init_db()
    except Exception as e:
        print(f"❌ Error creating tables: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 5: Verify tables exist
    print("\n5. Verifying tables in database...")
    try:
        from sqlalchemy import inspect
        from database import engine
        
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        
        expected_tables = [
            'users', 'meetings', 'speakers', 'transcripts',
            'summaries', 'sentiment_analysis', 'action_items', 'key_decisions'
        ]
        
        print(f"   Found {len(existing_tables)} tables in database:")
        for table in existing_tables:
            status = "✅" if table in expected_tables else "⚠️"
            print(f"   {status} {table}")
        
        missing_tables = set(expected_tables) - set(existing_tables)
        if missing_tables:
            print(f"\n   ⚠️ Missing tables: {', '.join(missing_tables)}")
            return False
        
    except Exception as e:
        print(f"❌ Error verifying tables: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Success!
    print("\n" + "=" * 60)
    print("✅ DATABASE SETUP COMPLETE!")
    print("=" * 60)
    print("\nYou can now run: python main_updated.py")
    print()
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)