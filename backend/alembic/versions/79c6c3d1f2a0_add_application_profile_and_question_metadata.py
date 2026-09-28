"""Add application profile and adaptive question metadata."""
from alembic import op
import sqlalchemy as sa

revision = "79c6c3d1f2a0"
down_revision = "268a2774496b"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("questions", sa.Column("section", sa.String(), nullable=True))
    op.add_column("questions", sa.Column("condition_logic", sa.JSON(), nullable=True))
    op.add_column("questions", sa.Column("options", sa.JSON(), nullable=True))
    op.create_table(
        "application_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False, unique=True),
        sa.Column("company_name", sa.String()), sa.Column("business_type", sa.String()),
        sa.Column("industry", sa.String()), sa.Column("years_in_operation", sa.Integer()),
        sa.Column("business_address", sa.String()), sa.Column("city", sa.String()),
        sa.Column("state", sa.String()), sa.Column("country", sa.String()), sa.Column("annual_revenue", sa.String()),
        sa.Column("property_address", sa.String()), sa.Column("property_type", sa.String()),
        sa.Column("property_value", sa.String()), sa.Column("ownership_type", sa.String()),
        sa.Column("property_operations", sa.Text()), sa.Column("employee_count", sa.Integer()),
    )
    op.create_index("ix_application_profiles_id", "application_profiles", ["id"])

def downgrade():
    op.drop_index("ix_application_profiles_id", table_name="application_profiles")
    op.drop_table("application_profiles")
    op.drop_column("questions", "options")
    op.drop_column("questions", "condition_logic")
    op.drop_column("questions", "section")
