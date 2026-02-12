#!/usr/bin/env python3
"""
Test script to diagnose the 422 signup error
Run this to identify the exact problem
"""

import sys
import json

print("=" * 60)
print("PAROT SIGNUP DIAGNOSTICS")
print("=" * 60)

# Test 1: Check if email-validator is installed
print("\n1. Checking email-validator installation...")
try:
    import email_validator
    print("   ✅ email-validator is installed (version: {})".format(email_validator.__version__))
except ImportError:
    print("   ❌ email-validator is NOT installed")
    print("   📝 Fix: pip install email-validator")
    sys.exit(1)

# Test 2: Check if pydantic can use EmailStr
print("\n2. Checking Pydantic EmailStr...")
try:
    from pydantic import BaseModel, EmailStr
    
    class TestUser(BaseModel):
        email: EmailStr
    
    # Test with valid email
    test = TestUser(email="test@example.com")
    print("   ✅ Pydantic EmailStr is working")
except Exception as e:
    print(f"   ❌ Pydantic EmailStr failed: {e}")
    sys.exit(1)

# Test 3: Test the actual UserCreate schema
print("\n3. Testing UserCreate schema...")
try:
    from database import schemas
    
    # Test valid data
    test_user = schemas.UserCreate(
        email="test@example.com",
        username="test",
        password="password123",
        full_name="Test User"
    )
    print("   ✅ UserCreate schema validation passed")
    print(f"   📧 Email: {test_user.email}")
    print(f"   👤 Username: {test_user.username}")
    
except Exception as e:
    print(f"   ❌ UserCreate schema validation failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test with different email formats
print("\n4. Testing various email formats...")
test_emails = [
    "user@example.com",
    "test.user@example.com",
    "user+tag@example.co.uk",
    "user_name@example-domain.com",
]

for email in test_emails:
    try:
        test_user = schemas.UserCreate(
            email=email,
            username="test",
            password="password123",
            full_name="Test"
        )
        print(f"   ✅ {email}")
    except Exception as e:
        print(f"   ❌ {email} - {e}")

# Test 5: Test database connection
print("\n5. Testing database connection...")
try:
    from database import test_connection
    if test_connection():
        print("   ✅ Database connection successful")
    else:
        print("   ⚠️  Database connection failed")
        print("   (This won't prevent signup API testing)")
except Exception as e:
    print(f"   ⚠️  Database test error: {e}")

# Test 6: Test the actual signup endpoint
print("\n6. Testing signup endpoint with requests...")
try:
    import requests
    
    test_data = {
        "email": "diagnostictest@example.com",
        "username": "diagnostictest",
        "password": "testpass123",
        "full_name": "Diagnostic Test User"
    }
    
    print(f"   📤 Sending POST to http://localhost:8000/api/auth/signup")
    print(f"   📦 Payload: {json.dumps({**test_data, 'password': '[REDACTED]'}, indent=2)}")
    
    response = requests.post(
        "http://localhost:8000/api/auth/signup",
        json=test_data,
        timeout=5
    )
    
    print(f"   📥 Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("   ✅ Signup endpoint is working!")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
    elif response.status_code == 422:
        print("   ❌ 422 Unprocessable Entity")
        print(f"   Error details: {json.dumps(response.json(), indent=2)}")
    elif response.status_code == 400:
        print("   ⚠️  400 Bad Request (might be duplicate email)")
        print(f"   Response: {json.dumps(response.json(), indent=2)}")
    else:
        print(f"   ❌ Unexpected status code: {response.status_code}")
        print(f"   Response: {response.text}")
        
except requests.exceptions.ConnectionError:
    print("   ❌ Cannot connect to backend at http://localhost:8000")
    print("   📝 Make sure your backend is running: python main.py")
except Exception as e:
    print(f"   ❌ Request failed: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTICS COMPLETE")
print("=" * 60)

# Summary and recommendations
print("\n📋 SUMMARY:")
print("\nIf all tests pass but signup still fails:")
print("1. Check browser console for the exact error message")
print("2. Check backend logs for detailed error info")
print("3. Try the updated SignupPage_Fixed.tsx for better error messages")
print("\nIf email-validator test failed:")
print("   Run: pip install email-validator")
print("\nIf database test failed:")
print("   Check your .env file and PostgreSQL connection")
print("\nIf endpoint test shows 422:")
print("   Look at the 'Error details' above to see which field is failing")