"""
Seed the database with a Commercial Property insurance product including:
- 5 questions
- 1 unconditional requirement
- 3 conditional requirements using nested rule logic
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.database import SessionLocal
from app.models.core import InsuranceProduct, Question, Requirement

def seed():
    db = SessionLocal()
    try:
        existing = db.query(InsuranceProduct).filter_by(name="Commercial Property").first()
        if existing:
            print("Seed data already exists – skipping.")
            return

        # --- Product ---
        product = InsuranceProduct(
            name="Commercial Property",
            description="Coverage for commercial buildings, contents, and business interruption."
        )
        db.add(product)
        db.flush()  # get product.id

        # --- Questions ---
        q_entity_type = Question(product_id=product.id, text="Type of business entity", field_type="text", is_required=True)
        q_revenue     = Question(product_id=product.id, text="Estimated annual revenue (INR)", field_type="number", is_required=True)
        q_hazmat      = Question(product_id=product.id, text="Are hazardous materials present on the premises?", field_type="yesno", is_required=True)
        q_prop_value  = Question(product_id=product.id, text="Estimated property value (INR)", field_type="number", is_required=True)
        q_risk_class  = Question(product_id=product.id, text="Risk classification (low/medium/high)", field_type="text", is_required=True)
        db.add_all([q_entity_type, q_revenue, q_hazmat, q_prop_value, q_risk_class])
        db.flush()

        # --- Requirements ---

        # 1. UNCONDITIONAL – always required
        req_application = Requirement(
            product_id=product.id,
            name="Completed Application Form",
            description="A signed and complete application form is always required.",
            rule_logic=None
        )

        # 2. CONDITIONAL – revenue > 10,000,000
        req_financial = Requirement(
            product_id=product.id,
            name="Financial Statement",
            description="Recent audited financial statement.",
            rule_logic={
                "operator": "AND",
                "conditions": [
                    {"question_id": q_revenue.id, "operator": ">", "value": 10000000}
                ],
                "explanation": "Financial statement required because annual revenue exceeds the configured threshold of ₹1 crore."
            }
        )

        # 3. CONDITIONAL – hazardous materials = yes
        req_hazmat = Requirement(
            product_id=product.id,
            name="Hazardous Material Declaration",
            description="Declaration of all hazardous materials on site.",
            rule_logic={
                "operator": "AND",
                "conditions": [
                    {"question_id": q_hazmat.id, "operator": "==", "value": "yes"}
                ],
                "explanation": "Hazardous material declaration required because hazardous materials are present on the premises."
            }
        )

        # 4. CONDITIONAL – nested: property value > 50,000,000 OR risk class == high
        req_valuation = Requirement(
            product_id=product.id,
            name="Professional Property Valuation Report",
            description="Independent valuation evidence from a certified surveyor.",
            rule_logic={
                "operator": "OR",
                "conditions": [
                    {"question_id": q_prop_value.id, "operator": ">", "value": 50000000},
                    {"question_id": q_risk_class.id,  "operator": "==", "value": "high"}
                ],
                "explanation": "Property valuation report required because the property value exceeds ₹5 crore or the risk is classified as high."
            }
        )

        db.add_all([req_application, req_financial, req_hazmat, req_valuation])
        db.commit()
        print(f"Seeded: product={product.id}, questions={[q_entity_type.id, q_revenue.id, q_hazmat.id, q_prop_value.id, q_risk_class.id]}")

    finally:
        db.close()

if __name__ == "__main__":
    seed()
