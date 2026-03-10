# Copyright (c) 2026 Anders Ødenes. All rights reserved.
"""Enable Row Level Security on organizations table

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-10

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE organizations ENABLE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY tenant_isolation ON organizations "
        "USING (tenant_id = current_setting('app.current_tenant')::UUID)"
    )
    op.execute("ALTER TABLE organizations FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    op.execute("ALTER TABLE organizations NO FORCE ROW LEVEL SECURITY")
    op.execute("DROP POLICY IF EXISTS tenant_isolation ON organizations")
    op.execute("ALTER TABLE organizations DISABLE ROW LEVEL SECURITY")
