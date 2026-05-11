"""add_articles_status_index

Revision ID: 71634f699e07
Revises: adc071621489
Create Date: 2026-05-11 09:52:37.680040

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71634f699e07'
down_revision: Union[str, Sequence[str], None] = 'adc071621489'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index("idx_articles_status", "articles", ["status", "generation_timestamp"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("idx_articles_status", table_name="articles")
