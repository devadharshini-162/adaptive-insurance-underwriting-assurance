"""add underwriter additional requests"""
from alembic import op
import sqlalchemy as sa

revision = "3f6b1ca4e9d0"
down_revision = "5c4f9e48d09a"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("additional_requests", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("submission_id", sa.Integer(), sa.ForeignKey("submissions.id"), nullable=False), sa.Column("request_type", sa.String(), nullable=False), sa.Column("document_name", sa.String()), sa.Column("message", sa.Text(), nullable=False), sa.Column("note", sa.Text()), sa.Column("status", sa.String(), nullable=False, server_default="open"), sa.Column("response_document_id", sa.Integer(), sa.ForeignKey("documents.id")), sa.Column("created_at", sa.DateTime()))
def downgrade():
    op.drop_table("additional_requests")
