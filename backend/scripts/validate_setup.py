#!/usr/bin/env python3
"""Validate backend setup and configuration."""
import sys
from pathlib import Path

# Add app to path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing imports...")
    try:
        from app.config import settings
        print("✅ Config module imported successfully")
        
        from app.main import app
        print("✅ Main app module imported successfully")
        
        from app.core.logging import setup_logging
        print("✅ Logging module imported successfully")
        
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_config():
    """Test configuration."""
    print("\nTesting configuration...")
    try:
        from app.config import settings
        
        print(f"  App Name: {settings.APP_NAME}")
        print(f"  Version: {settings.APP_VERSION}")
        print(f"  Environment: {settings.ENVIRONMENT}")
        print(f"  API Port: {settings.API_PORT}")
        print(f"  Debug Mode: {settings.DEBUG}")
        
        # Check required settings
        assert settings.APP_NAME, "APP_NAME not set"
        assert settings.DATABASE_URL, "DATABASE_URL not set"
        assert settings.REDIS_URL, "REDIS_URL not set"
        
        print("✅ Configuration validated successfully")
        return True
    except Exception as e:
        print(f"❌ Configuration validation failed: {e}")
        return False

def test_app_structure():
    """Test that all required directories exist."""
    print("\nTesting project structure...")
    
    required_dirs = [
        "app",
        "app/api",
        "app/api/v1",
        "app/core",
        "app/models",
        "app/schemas",
        "app/services",
        "app/tools",
        "app/db",
        "app/middleware",
        "app/utils",
        "tests",
        "tests/unit",
        "tests/integration",
        "tests/e2e",
        "scripts",
        "alembic",
        "alembic/versions",
    ]
    
    base_path = Path(__file__).parent.parent
    missing = []
    
    for dir_path in required_dirs:
        full_path = base_path / dir_path
        if not full_path.exists():
            missing.append(dir_path)
            print(f"  ❌ Missing: {dir_path}")
        else:
            print(f"  ✅ Found: {dir_path}")
    
    if missing:
        print(f"\n❌ Missing {len(missing)} directories")
        return False
    
    print("\n✅ All required directories exist")
    return True

def test_files():
    """Test that all required files exist."""
    print("\nTesting required files...")
    
    required_files = [
        "pyproject.toml",
        "docker-compose.yml",
        "Dockerfile",
        ".env.example",
        ".gitignore",
        "README.md",
        "app/__init__.py",
        "app/main.py",
        "app/config.py",
        "app/core/logging.py",
    ]
    
    base_path = Path(__file__).parent.parent
    missing = []
    
    for file_path in required_files:
        full_path = base_path / file_path
        if not full_path.exists():
            missing.append(file_path)
            print(f"  ❌ Missing: {file_path}")
        else:
            print(f"  ✅ Found: {file_path}")
    
    if missing:
        print(f"\n❌ Missing {len(missing)} files")
        return False
    
    print("\n✅ All required files exist")
    return True

def main():
    """Run all validation tests."""
    print("=" * 60)
    print("CDSA Backend Setup Validation")
    print("=" * 60)
    
    tests = [
        ("Project Structure", test_app_structure),
        ("Required Files", test_files),
        ("Python Imports", test_imports),
        ("Configuration", test_config),
    ]
    
    results = []
    for name, test_func in tests:
        print(f"\n{'=' * 60}")
        print(f"Running: {name}")
        print("=" * 60)
        results.append(test_func())
    
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    
    for i, (name, _) in enumerate(tests):
        status = "✅ PASSED" if results[i] else "❌ FAILED"
        print(f"{status}: {name}")
    
    if all(results):
        print("\n🎉 All validation tests passed!")
        print("\nNext steps:")
        print("1. Start Docker services: docker-compose up -d")
        print("2. Run the API: uvicorn app.main:app --reload")
        print("3. Access docs: http://localhost:8000/docs")
        return 0
    else:
        print("\n❌ Some validation tests failed. Please fix the issues above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())