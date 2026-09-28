"""upgrade legacy Commercial Property questions for adaptive risk intake"""

from alembic import op


revision = "8d91e4f6a2b3"
down_revision = "3f6b1ca4e9d0"
branch_labels = None
depends_on = None


def upgrade():
    # Earlier seed data predates question sections. Preserve the existing
    # questions/answers, but classify the risk questions so the adaptive UI
    # can present them in the Risk step.
    op.execute("""
        UPDATE questions q
        SET section = 'risk'
        FROM insurance_products p
        WHERE q.product_id = p.id
          AND p.name = 'Commercial Property'
          AND q.text IN (
              'Type of business entity',
              'Are hazardous materials present on the premises?',
              'Risk classification (low/medium/high)'
          )
    """)
    op.execute("""
        UPDATE questions q
        SET options = CAST('["low", "medium", "high"]' AS json)
        FROM insurance_products p
        WHERE q.product_id = p.id
          AND p.name = 'Commercial Property'
          AND q.text = 'Risk classification (low/medium/high)'
    """)
    op.execute("""
        DO $$
        DECLARE product_key integer;
        DECLARE manufacturing_key integer;
        BEGIN
          SELECT id INTO product_key FROM insurance_products
          WHERE name = 'Commercial Property' LIMIT 1;
          IF product_key IS NULL THEN RETURN; END IF;

          SELECT id INTO manufacturing_key FROM questions
          WHERE product_id = product_key
            AND text = 'Is manufacturing carried out at this property?'
          LIMIT 1;
          IF manufacturing_key IS NULL THEN
            INSERT INTO questions (product_id, text, field_type, is_required, section)
            VALUES (product_key, 'Is manufacturing carried out at this property?', 'yesno', true, 'risk')
            RETURNING id INTO manufacturing_key;
          END IF;

          IF NOT EXISTS (SELECT 1 FROM questions WHERE product_id = product_key AND text = 'What fire protection is in place?') THEN
            INSERT INTO questions (product_id, text, field_type, is_required, section, condition_logic, options)
            VALUES (product_key, 'What fire protection is in place?', 'select', true, 'risk',
                    json_build_object('question_id', manufacturing_key, 'operator', '==', 'value', 'yes'),
                    CAST('["Sprinkler system", "Fire extinguishers", "Alarm system", "None"]' AS json));
          END IF;

          IF NOT EXISTS (SELECT 1 FROM questions WHERE product_id = product_key AND text = 'Have there been property claims in the past five years?') THEN
            INSERT INTO questions (product_id, text, field_type, is_required, section)
            VALUES (product_key, 'Have there been property claims in the past five years?', 'yesno', true, 'risk');
          END IF;
        END $$;
    """)


def downgrade():
    # This is an additive data repair. Existing answers must not be deleted.
    pass
