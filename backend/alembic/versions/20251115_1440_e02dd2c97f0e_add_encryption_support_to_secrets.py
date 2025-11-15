"""add_encryption_support_to_secrets

Revision ID: e02dd2c97f0e
Revises: 001
Create Date: 2025-11-15 14:40:58.990917

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e02dd2c97f0e'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add encryption support columns to secrets table."""
    # Add is_encrypted column to track encryption status
    op.add_column('secrets', sa.Column('is_encrypted', sa.Boolean(), nullable=False, server_default='true'))
    
    # Add comment for documentation
    op.execute("""
        COMMENT ON COLUMN secrets.is_encrypted IS
        'Indicates if the secret value is encrypted. All new secrets are encrypted by default.'
    """)
    
    # All existing secrets should be marked as encrypted since we're using property-based encryption
    # The encryption happens automatically through the Secret.value property


def downgrade() -> None:
    """Remove encryption support columns."""
    op.drop_column('secrets', 'is_encrypted')