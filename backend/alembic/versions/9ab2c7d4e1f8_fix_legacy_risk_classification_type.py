"""render legacy risk classification as a fixed choice"""

from alembic import op


revision = "9ab2c7d4e1f8"
down_revision = "8d91e4f6a2b3"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        UPDATE questions q
        SET field_type = 'select',
            options = CAST('["low", "medium", "high"]' AS json)
        FROM insurance_products p
        WHERE q.product_id = p.id
          AND p.name = 'Commercial Property'
          AND q.text = 'Risk classification (low/medium/high)'
    """)


def downgrade():
    op.execute("""
        UPDATE questions q
        SET field_type = 'text', options = NULL
        FROM insurance_products p
        WHERE q.product_id = p.id
          AND p.name = 'Commercial Property'
          AND q.text = 'Risk classification (low/medium/high)'
    """)
