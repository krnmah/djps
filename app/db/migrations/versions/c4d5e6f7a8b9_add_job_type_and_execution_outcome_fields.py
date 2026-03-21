"""add job type and execution outcome fields

Revision ID: c4d5e6f7a8b9
Revises: a1b2c3d4e5f6
Create Date: 2026-03-21 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    job_type_enum = sa.Enum("http_request", "email_send", name="jobtype")
    job_type_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "jobs",
        sa.Column(
            "job_type",
            job_type_enum,
            nullable=False,
            server_default="http_request",
        ),
    )
    op.add_column(
        "jobs",
        sa.Column("result_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column("jobs", sa.Column("error_code", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("error_message", sa.String(), nullable=True))
    op.add_column("jobs", sa.Column("completed_at", sa.DateTime(), nullable=True))

    op.create_index(
        "idx_jobs_job_type_status_created_at",
        "jobs",
        ["job_type", "status", "created_at"],
    )

    op.alter_column("jobs", "job_type", server_default=None)


def downgrade() -> None:
    op.drop_index("idx_jobs_job_type_status_created_at", table_name="jobs")

    op.drop_column("jobs", "completed_at")
    op.drop_column("jobs", "error_message")
    op.drop_column("jobs", "error_code")
    op.drop_column("jobs", "result_json")
    op.drop_column("jobs", "job_type")

    job_type_enum = sa.Enum("http_request", "email_send", name="jobtype")
    job_type_enum.drop(op.get_bind(), checkfirst=True)
