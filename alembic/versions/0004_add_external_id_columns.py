# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Add external_id to locations and jobs

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-10

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("locations", sa.Column("external_id", sa.String(255), nullable=True))
    op.create_index("ix_locations_external_id", "locations", ["external_id"])

    op.add_column("jobs", sa.Column("external_id", sa.String(255), nullable=True))
    op.create_index("ix_jobs_external_id", "jobs", ["external_id"])


def downgrade() -> None:
    op.drop_index("ix_jobs_external_id", table_name="jobs")
    op.drop_column("jobs", "external_id")

    op.drop_index("ix_locations_external_id", table_name="locations")
    op.drop_column("locations", "external_id")
