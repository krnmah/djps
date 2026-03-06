"""add indexes to jobs table

Revision ID: a1b2c3d4e5f6
Revises: b371a3467b07
Create Date: 2026-03-06 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "b371a3467b07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_created_at", "jobs", ["created_at"])
    op.create_index("idx_jobs_status_created_at", "jobs", ["status", "created_at"])
    op.create_index("idx_jobs_last_attempt_at", "jobs", ["last_attempt_at"])


def downgrade() -> None:
    op.drop_index("idx_jobs_last_attempt_at", table_name="jobs")
    op.drop_index("idx_jobs_status_created_at", table_name="jobs")
    op.drop_index("idx_jobs_created_at", table_name="jobs")
    op.drop_index("idx_jobs_status", table_name="jobs")
