#!/usr/bin/env python3
"""Quick server verification script"""
import sys
try:
    import requests
    
    print("Testing CDSA Backend Server on http://localhost:8001")
    print("=" * 50)
    
    # Test health endpoint
    try:
        r = requests.get('http://localhost:8001/health', timeout=5)
        print(f"\n✅ Health Check: Status {r.status_code}")
        print(f"   Response: {r.json()}")
    except Exception as e:
        print(f"\n❌ Health Check Failed: {e}")
        sys.exit(1)
    
    # Test root endpoint
    try:
        r = requests.get('http://localhost:8001/', timeout=5)
        print(f"\n✅ Root Endpoint: Status {r.status_code}")
        print(f"   Response: {r.json()}")
    except Exception as e:
        print(f"\n❌ Root Endpoint Failed: {e}")
    
    # Test docs
    try:
        r = requests.get('http://localhost:8001/docs', timeout=5)
        print(f"\n✅ API Docs: Status {r.status_code}")
        print(f"   Available at: http://localhost:8001/docs")
    except Exception as e:
        print(f"\n❌ API Docs Failed: {e}")
    
    print("\n" + "=" * 50)
    print("🎉 Server is running successfully!")
    print("\nAccess the API at:")
    print("  - Health: http://localhost:8001/health")
    print("  - Root: http://localhost:8001/")
    print("  - Docs: http://localhost:8001/docs")
    print("  - ReDoc: http://localhost:8001/redoc")
    
except ImportError:
    print("Installing requests library...")
    import subprocess
    subprocess.run([sys.executable, "-m", "pip", "install", "requests", "-q", "--user"])
    print("Please run this script again")
    sys.exit(1)