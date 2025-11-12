"""
Seed data script for initializing database with default roles, permissions, and admin user.

Run this script after database migrations to set up the initial system state.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).resolve().parents[1]))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import init_db
from app.models.user import User, Role, Permission
from app.core.security import get_password_hash
from app.config import settings


# Default Permissions
DEFAULT_PERMISSIONS = [
    # User Management
    {"name": "users:create", "description": "Create new users"},
    {"name": "users:read", "description": "View users"},
    {"name": "users:update", "description": "Update users"},
    {"name": "users:delete", "description": "Delete users"},
    
    # Role Management
    {"name": "roles:manage", "description": "Manage roles and permissions"},
    
    # Chat
    {"name": "chat:create", "description": "Create chat sessions"},
    {"name": "chat:read", "description": "View chat history"},
    {"name": "chat:delete", "description": "Delete chat sessions"},
    
    # Tools
    {"name": "tools:execute", "description": "Execute tools"},
    {"name": "tools:manage", "description": "Manage tool registry"},
    {"name": "tools:approve", "description": "Approve tool executions"},
    
    # Documents
    {"name": "documents:upload", "description": "Upload documents"},
    {"name": "documents:read", "description": "Read documents"},
    {"name": "documents:delete", "description": "Delete documents"},
    {"name": "documents:manage", "description": "Manage document settings"},
    
    # Secrets Vault
    {"name": "vault:read", "description": "Read secrets"},
    {"name": "vault:write", "description": "Create/update secrets"},
    {"name": "vault:delete", "description": "Delete secrets"},
    {"name": "vault:manage", "description": "Manage vault settings"},
    
    # Audit
    {"name": "audit:read", "description": "View audit logs"},
    {"name": "audit:export", "description": "Export audit logs"},
    
    # Notifications
    {"name": "notifications:read", "description": "View notifications"},
    {"name": "notifications:broadcast", "description": "Send broadcast notifications"},
    
    # LLM Gateway
    {"name": "llm:use", "description": "Use LLM services"},
    {"name": "llm:manage", "description": "Manage LLM settings"},
]

# Default Roles
DEFAULT_ROLES = {
    "ADMIN": {
        "description": "System administrator with full access",
        "permissions": [
            "users:create", "users:read", "users:update", "users:delete",
            "roles:manage",
            "chat:create", "chat:read", "chat:delete",
            "tools:execute", "tools:manage", "tools:approve",
            "documents:upload", "documents:read", "documents:delete", "documents:manage",
            "vault:read", "vault:write", "vault:delete", "vault:manage",
            "audit:read", "audit:export",
            "notifications:read", "notifications:broadcast",
            "llm:use", "llm:manage",
        ]
    },
    "MANAGER": {
        "description": "Manager with approval and oversight permissions",
        "permissions": [
            "users:read",
            "chat:create", "chat:read",
            "tools:execute", "tools:approve",
            "documents:upload", "documents:read",
            "vault:read", "vault:write",
            "audit:read",
            "notifications:read",
            "llm:use",
        ]
    },
    "ANALYST": {
        "description": "Standard analyst with core functionality access",
        "permissions": [
            "chat:create", "chat:read",
            "tools:execute",
            "documents:upload", "documents:read",
            "vault:read",
            "notifications:read",
            "llm:use",
        ]
    },
    "VIEWER": {
        "description": "Read-only access for viewing data",
        "permissions": [
            "chat:read",
            "documents:read",
            "audit:read",
            "notifications:read",
        ]
    }
}


async def create_permissions(db: AsyncSession) -> dict[str, Permission]:
    """Create default permissions."""
    print("Creating permissions...")
    permissions_map = {}
    
    for perm_data in DEFAULT_PERMISSIONS:
        # Check if permission exists
        result = await db.execute(
            select(Permission).where(Permission.name == perm_data["name"])
        )
        permission = result.scalar_one_or_none()
        
        if permission is None:
            permission = Permission(
                name=perm_data["name"],
                description=perm_data["description"]
            )
            db.add(permission)
            print(f"  ✓ Created permission: {perm_data['name']}")
        else:
            print(f"  • Permission already exists: {perm_data['name']}")
        
        permissions_map[perm_data["name"]] = permission
    
    await db.commit()
    return permissions_map


async def create_roles(db: AsyncSession, permissions_map: dict[str, Permission]) -> dict[str, Role]:
    """Create default roles and assign permissions."""
    print("\nCreating roles...")
    roles_map = {}
    
    for role_name, role_data in DEFAULT_ROLES.items():
        # Check if role exists
        result = await db.execute(
            select(Role).where(Role.name == role_name)
        )
        role = result.scalar_one_or_none()
        
        if role is None:
            role = Role(
                name=role_name,
                description=role_data["description"]
            )
            db.add(role)
            print(f"  ✓ Created role: {role_name}")
        else:
            print(f"  • Role already exists: {role_name}")
        
        # Assign permissions to role
        role.permissions = []
        for perm_name in role_data["permissions"]:
            if perm_name in permissions_map:
                role.permissions.append(permissions_map[perm_name])
        
        roles_map[role_name] = role
    
    await db.commit()
    return roles_map


async def create_admin_user(db: AsyncSession, roles_map: dict[str, Role]):
    """Create default admin user."""
    print("\nCreating admin user...")
    
    admin_email = "admin@cdsa.local"
    admin_username = "admin"
    
    # Check if admin user exists
    result = await db.execute(
        select(User).where(User.email == admin_email)
    )
    admin_user = result.scalar_one_or_none()
    
    if admin_user is None:
        # Create admin user
        admin_user = User(
            email=admin_email,
            username=admin_username,
            hashed_password=get_password_hash("admin123"),  # Default password
            full_name="System Administrator",
            is_active=True,
            is_superuser=True,
            is_verified=True
        )
        
        # Assign ADMIN role
        if "ADMIN" in roles_map:
            admin_user.roles.append(roles_map["ADMIN"])
        
        db.add(admin_user)
        await db.commit()
        
        print(f"  ✓ Created admin user: {admin_email}")
        print(f"    Username: {admin_username}")
        print(f"    Password: admin123")
        print(f"    ⚠️  IMPORTANT: Change this password immediately!")
    else:
        print(f"  • Admin user already exists: {admin_email}")


async def seed_database():
    """Main function to seed the database."""
    print("=" * 60)
    print("CDSA Database Seeding")
    print("=" * 60)
    
    try:
        # Initialize database
        print("\nInitializing database connection...")
        engine, session_factory = init_db()
        print("✓ Database connection established")
        
        # Create session
        async with session_factory() as db:
            # Create permissions
            permissions_map = await create_permissions(db)
            
            # Create roles
            roles_map = await create_roles(db, permissions_map)
            
            # Create admin user
            await create_admin_user(db, roles_map)
        
        print("\n" + "=" * 60)
        print("✓ Database seeding completed successfully!")
        print("=" * 60)
        
        print("\n📝 Summary:")
        print(f"  • Permissions: {len(DEFAULT_PERMISSIONS)}")
        print(f"  • Roles: {len(DEFAULT_ROLES)}")
        print(f"  • Admin user: admin@cdsa.local")
        
        print("\n🔐 Default Credentials:")
        print("  Email: admin@cdsa.local")
        print("  Username: admin")
        print("  Password: admin123")
        print("\n  ⚠️  IMPORTANT: Change the admin password immediately!")
        
    except Exception as e:
        print(f"\n❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(seed_database())