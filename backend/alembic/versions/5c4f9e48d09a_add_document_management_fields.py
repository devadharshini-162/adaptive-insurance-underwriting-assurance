"""add customer-safe document metadata and replacement linkage"""

from alembic import op
import sqlalchemy as sa

revision = "5c4f9e48d09a"
down_revision = "79c6c3d1f2a0"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("documents", sa.Column("original_filename", sa.String(), nullable=True))
    op.add_column("documents", sa.Column("replaced_by_document_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_documents_replaced_by_document", "documents", "documents", ["replaced_by_document_id"], ["id"])

def downgrade():
    op.drop_constraint("fk_documents_replaced_by_document", "documents", type_="foreignkey")
    op.drop_column("documents", "replaced_by_document_id")
    op.drop_column("documents", "original_filename")
