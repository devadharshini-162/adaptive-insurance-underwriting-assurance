"""add optional user profile fields"""
from alembic import op
import sqlalchemy as sa
revision = "c2a9f7e4d6b1"
down_revision = "9ab2c7d4e1f8"
branch_labels = None
depends_on = None
def upgrade():
    op.add_column("users", sa.Column("phone", sa.String(), nullable=True))
    op.add_column("users", sa.Column("organization", sa.String(), nullable=True))
    op.add_column("users", sa.Column("job_title", sa.String(), nullable=True))
def downgrade():
    op.drop_column("users", "job_title")
    op.drop_column("users", "organization")
    op.drop_column("users", "phone")
