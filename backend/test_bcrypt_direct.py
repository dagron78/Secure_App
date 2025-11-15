"""Direct bcrypt test to isolate the issue."""
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# The actual hash from the database
stored_hash = "$2b$12$ms4TLSnVueN0WVpXQ3vem.Yo0IGyL38K3qD.JgJitK/XmpPdESfMK"
password = "admin123"

print(f"Password: {password}")
print(f"Password length: {len(password)}")
print(f"Hash: {stored_hash}")
print(f"Hash length: {len(stored_hash)}")

try:
    result = pwd_context.verify(password, stored_hash)
    print(f"✓ Verification result: {result}")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()