"""add_gin_indexes

Revision ID: 6558ed8e17fb
Revises: aa33e5fe355c
Create Date: 2026-10-08 12:58:02.676244

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '6558ed8e17fb'
down_revision: Union[str, Sequence[str], None] = 'aa33e5fe355c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # GIN indexes are Postgres specific. Guard for SQLite.
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute(sa.text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

        # GIN indexes for fuzzy search on name, email, and course
        op.execute(sa.text("CREATE INDEX ix_certs_recipient_name_gin ON certificates USING gin (recipient_name gin_trgm_ops)"))
        op.execute(sa.text("LOWER(recipient_email) as email_lower")) # This is a placeholder for the functional index
        op.execute(sa.text("CREATE INDEX ix_certs_email_lower_gin ON certificates USING gin (LOWER(recipient_email) gin_trgm_ops)"))
        op.execute(sa.text("CREATE INDEX ix_certs_course_name_gin ON certificates USING gin (course_name gin_trgm_ops)"))

def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == 'postgresql':
        op.execute(sa.text("DROP INDEX ix_certs_recipient_name_gin"))
        op.execute(sa.text("DROP INDEX ix_certs_email_lower_gin"))
        op.execute(sa.text("DROP INDEX ix_certs_course_name_gin"))
