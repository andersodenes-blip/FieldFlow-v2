# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Add home_latitude and home_longitude to technicians table

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("technicians", sa.Column("home_latitude", sa.Float(), nullable=True))
    op.add_column("technicians", sa.Column("home_longitude", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("technicians", "home_longitude")
    op.drop_column("technicians", "home_latitude")
