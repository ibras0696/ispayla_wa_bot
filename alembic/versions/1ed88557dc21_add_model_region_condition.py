"""add model region condition

Revision ID: 1ed88557dc21
Revises: 
Create Date: 2025-12-20 00:27:56.181228

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1ed88557dc21'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column("ads", sa.Column("model_name", sa.String(length=100), nullable=True))
    op.add_column("ads", sa.Column("region", sa.String(length=100), nullable=True))
    op.add_column("ads", sa.Column("condition", sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("ads", "condition")
    op.drop_column("ads", "region")
    op.drop_column("ads", "model_name")
