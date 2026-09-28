"""add demonstration insurers and underwriter assignment fields"""

from alembic import op
import sqlalchemy as sa


revision = "f4c8d3a1b2e7"
down_revision = "c2a9f7e4d6b1"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "insurance_companies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_demo", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_insurance_companies_name", "insurance_companies", ["name"])
    op.add_column("users", sa.Column("insurance_company_id", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("supported_product_ids", sa.JSON(), nullable=True))
    op.add_column("users", sa.Column("specialization", sa.String(), nullable=True))
    op.add_column("users", sa.Column("years_experience", sa.Integer(), nullable=True))
    op.add_column("users", sa.Column("availability_status", sa.String(), nullable=True))
    op.add_column("users", sa.Column("professional_description", sa.Text(), nullable=True))
    op.create_foreign_key("fk_users_insurance_company", "users", "insurance_companies", ["insurance_company_id"], ["id"])
    op.add_column("submissions", sa.Column("insurance_company_id", sa.Integer(), nullable=True))
    op.add_column("submissions", sa.Column("assigned_underwriter_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_submissions_insurance_company", "submissions", "insurance_companies", ["insurance_company_id"], ["id"])
    op.create_foreign_key("fk_submissions_assigned_underwriter", "submissions", "users", ["assigned_underwriter_id"], ["id"])


def downgrade():
    op.drop_constraint("fk_submissions_assigned_underwriter", "submissions", type_="foreignkey")
    op.drop_constraint("fk_submissions_insurance_company", "submissions", type_="foreignkey")
    op.drop_column("submissions", "assigned_underwriter_id")
    op.drop_column("submissions", "insurance_company_id")
    op.drop_constraint("fk_users_insurance_company", "users", type_="foreignkey")
    for column in ("professional_description", "availability_status", "years_experience", "specialization", "supported_product_ids", "insurance_company_id"):
        op.drop_column("users", column)
    op.drop_index("ix_insurance_companies_name", table_name="insurance_companies")
    op.drop_table("insurance_companies")
