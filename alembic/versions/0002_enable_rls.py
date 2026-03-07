"""Enable Row Level Security on all tenant tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-07

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

RLS_TABLES = [
    "users",
    "regions",
    "technicians",
    "customers",
    "locations",
    "service_contracts",
    "jobs",
    "scheduled_visits",
    "routes",
    "route_visits",
    "import_jobs",
    "audit_events",
]


def upgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_isolation ON {table} "
            f"USING (tenant_id = current_setting('app.current_tenant')::UUID)"
        )
    # The app user should not be a superuser so RLS applies.
    # For the app connection, FORCE RLS so even table owners are subject to it.
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")


def downgrade() -> None:
    for table in RLS_TABLES:
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
