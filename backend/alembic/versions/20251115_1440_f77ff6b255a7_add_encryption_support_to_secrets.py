"""add_encryption_support_to_secrets

Revision ID: f77ff6b255a7
Revises: 001
Create Date: 2025-11-15 14:40:58.990868

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f77ff6b255a7'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass