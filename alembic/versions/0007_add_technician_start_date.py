# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Add start_date to technicians table

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("technicians", sa.Column("start_date", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("technicians", "start_date")
