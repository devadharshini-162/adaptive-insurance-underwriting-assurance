"""Idempotently provision the prototype's deterministic product catalogue."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.db.database import SessionLocal
from datetime import datetime, timedelta

from app.models.core import (
    ApplicationProfile, Answer, AuditRecord, InsuranceCompany,
    InsuranceProduct, Question, Requirement, Submission, UnderwritingIssue, User,
)
from app.db.product_catalog import CATALOG
from app.core.security import get_password_hash


DEMO_COMPANIES = [
    ("ApexShield Insurance", "Demonstration insurer for motor, commercial and technology cover."),
    ("HorizonSure Insurance", "Demonstration insurer for property, construction, motor and travel cover."),
    ("SecureNest General Insurance", "Demonstration insurer for home, property and marine cargo cover."),
    ("NovaCover Insurance", "Demonstration insurer for cyber, travel and personal insurance cover."),
]

DEMO_UNDERWRITERS = [
    ("ananya.rao@demo.insurance", "Ananya Rao", "ApexShield Insurance", "Commercial Lines Underwriter", ["Motor Insurance", "Commercial Property", "General Liability"], "Motor and commercial insurance", 10, "available", "Reviews fleet, commercial property and general liability applications."),
    ("priya.nair@demo.insurance", "Priya Nair", "ApexShield Insurance", "Technology Risk Underwriter", ["Cyber Insurance", "Personal Cyber Protection", "Professional Liability / E&O", "Crime / Fidelity"], "Cyber and technology risks", 8, "available", "Focuses on cyber controls, professional services and technology risk evidence."),
    ("rahul.menon@demo.insurance", "Rahul Menon", "HorizonSure Insurance", "Property Underwriter", ["Commercial Property", "Construction Insurance"], "Property and construction risks", 12, "available", "Specialises in buildings, worksites and construction project exposures."),
    ("meera.krishnan@demo.insurance", "Meera Krishnan", "HorizonSure Insurance", "Personal Lines Underwriter", ["Motor Insurance", "Travel Insurance"], "Motor and travel insurance", 7, "available", "Reviews private motor and travel applications with a customer-focused approach."),
    ("arjun.kumar@demo.insurance", "Arjun Kumar", "SecureNest General Insurance", "Marine Underwriter", ["Marine Cargo Insurance", "Inland Marine / Goods & Equipment", "Personal Valuables & Marine"], "Marine cargo and personal valuables", 11, "available", "Assesses cargo transit, stock and equipment exposures."),
    ("kavya.iyer@demo.insurance", "Kavya Iyer", "SecureNest General Insurance", "Home and Property Underwriter", ["Home Insurance", "Commercial Property"], "Home and property insurance", 9, "available", "Reviews residential and small commercial property submissions."),
    ("rohan.das@demo.insurance", "Rohan Das", "NovaCover Insurance", "Specialty Underwriter", ["Cyber Insurance", "Professional Liability / E&O"], "Cyber and technology risks", 8, "available", "Focuses on digital resilience and professional technology exposures."),
    ("nisha.thomas@demo.insurance", "Nisha Thomas", "NovaCover Insurance", "Personal Insurance Underwriter", ["Travel Insurance", "Home Insurance", "Personal Liability Protection"], "Travel and personal insurance", 6, "available", "Reviews travel, personal liability and household cover with attention to clear customer communication."),
]

DEMO_CUSTOMERS = [
    ("customer1@example.com", "Aarav Patel", "+91 90000 10001", "Maple Mobility Services"),
    ("customer2@example.com", "Diya Shah", "+91 90000 10002", "BluePeak Digital Studio"),
    ("customer3@example.com", "Kabir Singh", "+91 90000 10003", "Summit Works Private Limited"),
    ("customer4@example.com", "Meera Joshi", "+91 90000 10004", "Harbor Home Services"),
    ("customer5@example.com", "Riya Nanda", "+91 90000 10005", "Northwind Traders"),
]

# Each record is deliberately fictional and is keyed by a stable demo label,
# making the seed rerunnable without duplicating applications.
DEMO_SUBMISSIONS = [
    ("motor-draft", "customer1@example.com", "Motor Insurance", "ApexShield Insurance", "ananya.rao@demo.insurance", "draft", {"company_name": "Aarav Patel", "business_address": "12 Lake View Road", "city": "Pune", "state": "Maharashtra", "country": "India"}, 2),
    ("cyber-review", "customer2@example.com", "Cyber Insurance", "ApexShield Insurance", "priya.nair@demo.insurance", "under_review", {"company_name": "BluePeak Digital Studio", "business_type": "Private limited company", "industry": "Software services", "city": "Bengaluru", "state": "Karnataka", "country": "India", "annual_revenue": "18000000"}, 9),
    ("property-review", "customer3@example.com", "Commercial Property", "HorizonSure Insurance", "rahul.menon@demo.insurance", "under_review", {"company_name": "Summit Works Private Limited", "business_type": "Construction", "industry": "Commercial construction", "city": "Chennai", "state": "Tamil Nadu", "country": "India", "annual_revenue": "42000000", "property_address": "48 Industrial Estate", "property_type": "Warehouse", "property_value": "65000000", "ownership_type": "Owned", "employee_count": 36}, 12),
    ("travel-draft", "customer4@example.com", "Travel Insurance", "HorizonSure Insurance", "meera.krishnan@demo.insurance", "draft", {"company_name": "Meera Joshi", "business_address": "24 Garden Street", "city": "Kochi", "state": "Kerala", "country": "India"}, 1),
    ("construction-review", "customer3@example.com", "Construction Insurance", "HorizonSure Insurance", "rahul.menon@demo.insurance", "under_review", {"company_name": "Summit Works Private Limited", "business_type": "Construction", "industry": "Infrastructure", "city": "Chennai", "state": "Tamil Nadu", "country": "India", "annual_revenue": "42000000"}, 16),
    ("home-action", "customer4@example.com", "Home Insurance", "SecureNest General Insurance", "kavya.iyer@demo.insurance", "info_requested", {"company_name": "Meera Joshi", "business_address": "24 Garden Street", "city": "Kochi", "state": "Kerala", "country": "India"}, 6),
    ("marine-approved", "customer5@example.com", "Marine Cargo Insurance", "SecureNest General Insurance", "arjun.kumar@demo.insurance", "approved", {"company_name": "Northwind Traders", "business_type": "Trading", "industry": "Consumer goods import", "city": "Mumbai", "state": "Maharashtra", "country": "India", "annual_revenue": "30000000"}, 21),
    ("cyber-specialty-review", "customer2@example.com", "Cyber Insurance", "NovaCover Insurance", "rohan.das@demo.insurance", "under_review", {"company_name": "BluePeak Digital Studio", "business_type": "Private limited company", "industry": "Software services", "city": "Bengaluru", "state": "Karnataka", "country": "India", "annual_revenue": "18000000"}, 4),
    ("travel-action", "customer5@example.com", "Travel Insurance", "NovaCover Insurance", "nisha.thomas@demo.insurance", "info_requested", {"company_name": "Riya Nanda", "business_address": "9 Orchard Lane", "city": "Delhi", "state": "Delhi", "country": "India"}, 7),
    ("home-approved", "customer1@example.com", "Home Insurance", "SecureNest General Insurance", "kavya.iyer@demo.insurance", "approved", {"company_name": "Aarav Patel", "business_address": "12 Lake View Road", "city": "Pune", "state": "Maharashtra", "country": "India"}, 28),
]

DEMO_PASSWORD = "DemoInsurance2026!"


def _rule(question_id, operator, value, explanation):
    return {"question_id": question_id, "operator": operator, "value": value, "explanation": explanation}


def seed(db=None):
    own_session = db is None
    db = db or SessionLocal()
    try:
        for spec in CATALOG:
            product = db.query(InsuranceProduct).filter_by(name=spec["name"]).first()
            if not product:
                product = InsuranceProduct(name=spec["name"], description=spec["description"])
                db.add(product); db.flush()
            else:
                product.description = spec["description"]

            questions = {question.text: question for question in product.questions}
            keys = {}
            for key, text, field_type, conditional in spec["questions"]:
                question = questions.get(text)
                if not question:
                    question = Question(product_id=product.id, text=text, field_type=field_type, is_required=True, section="risk")
                    db.add(question); db.flush(); questions[text] = question
                question.field_type = field_type
                question.section = "questions" if conditional and conditional[0] else "risk"
                if conditional and conditional[2]: question.options = conditional[2]
                keys[key] = question
            for key, text, _, conditional in spec["questions"]:
                if conditional and conditional[0]:
                    trigger, value, _ = conditional
                    keys[key].condition_logic = {"question_id": keys[trigger].id, "operator": ">" if isinstance(value, str) and value.startswith(">") else "==", "value": value[1:] if isinstance(value, str) and value.startswith(">") else value}
                else:
                    keys[key].condition_logic = None

            requirements = {requirement.name: requirement for requirement in product.requirements}
            for name, description, condition in spec["requirements"]:
                requirement = requirements.get(name)
                if not requirement:
                    requirement = Requirement(product_id=product.id, name=name, description=description)
                    db.add(requirement)
                requirement.description = description
                if condition:
                    trigger, value = condition
                    requirement.rule_logic = _rule(keys[trigger].id, ">" if isinstance(value, str) and value.startswith(">") else "==", value[1:] if isinstance(value, str) and value.startswith(">") else value, description)
                else:
                    requirement.rule_logic = None

        companies = {}
        for name, description in DEMO_COMPANIES:
            company = db.query(InsuranceCompany).filter_by(name=name).first()
            if not company:
                company = InsuranceCompany(name=name, description=description, is_demo=True)
                db.add(company); db.flush()
            else:
                company.description = description
                company.is_demo = True
            companies[name] = company

        products_by_name = {product.name: product.id for product in db.query(InsuranceProduct).all()}
        for email, name, company_name, title, product_names, specialization, years, availability, description in DEMO_UNDERWRITERS:
            underwriter = db.query(User).filter_by(email=email).first()
            if not underwriter:
                # These are clearly labelled demonstration accounts used to
                # populate the assignment catalogue, not production users.
                underwriter = User(email=email, password_hash=get_password_hash(DEMO_PASSWORD), name=name, role="underwriter")
                db.add(underwriter); db.flush()
            else:
                # Keep the documented local-only credentials reproducible.
                underwriter.password_hash = get_password_hash(DEMO_PASSWORD)
            underwriter.name = name
            underwriter.role = "underwriter"
            underwriter.insurance_company_id = companies[company_name].id
            underwriter.organization = company_name
            underwriter.job_title = title
            underwriter.supported_product_ids = [products_by_name[product] for product in product_names if product in products_by_name]
            underwriter.specialization = specialization
            underwriter.years_experience = years
            underwriter.availability_status = availability
            underwriter.professional_description = description

        customers = {}
        for email, name, phone, organization in DEMO_CUSTOMERS:
            customer = db.query(User).filter_by(email=email).first()
            if not customer:
                customer = User(email=email, password_hash=get_password_hash(DEMO_PASSWORD), name=name, role="customer")
                db.add(customer); db.flush()
            else:
                customer.password_hash = get_password_hash(DEMO_PASSWORD)
            customer.name = name
            customer.role = "customer"
            customer.phone = phone
            customer.organization = organization
            customer.job_title = "Demonstration customer"
            customers[email] = customer

        underwriters_by_email = {underwriter.email: underwriter for underwriter in db.query(User).filter(User.role == "underwriter").all()}
        for label, customer_email, product_name, company_name, underwriter_email, status, profile_values, days_ago in DEMO_SUBMISSIONS:
            # The audit creation record is the stable marker for a seeded
            # demonstration submission, avoiding changes to customer-created
            # data even when the same product is chosen.
            submission = next((
                audit.submission
                for audit in db.query(AuditRecord).filter(AuditRecord.action == "demo_submission_seeded").all()
                if (audit.context_data or {}).get("label") == label
            ), None)
            if submission:
                continue
            product = db.query(InsuranceProduct).filter_by(name=product_name).one()
            company = companies[company_name]
            underwriter = underwriters_by_email[underwriter_email]
            if underwriter.insurance_company_id != company.id or product.id not in (underwriter.supported_product_ids or []):
                raise ValueError(f"Invalid demonstration assignment for {label}")
            created_at = datetime.utcnow() - timedelta(days=days_ago)
            submission = Submission(
                user_id=customers[customer_email].id,
                product_id=product.id,
                insurance_company_id=company.id,
                assigned_underwriter_id=underwriter.id,
                status=status,
                created_at=created_at,
            )
            db.add(submission); db.flush()
            db.add(ApplicationProfile(submission_id=submission.id, **profile_values))
            # Answers use existing question records and are intentionally
            # minimal; they make the demo detail view useful without claiming
            # that a real document was uploaded.
            for question in product.questions[:2]:
                value = "no" if question.field_type == "yesno" else (question.options[0] if question.field_type == "select" and question.options else "Demonstration response")
                db.add(Answer(submission_id=submission.id, question_id=question.id, value=str(value)))
            db.add(AuditRecord(submission_id=submission.id, action="demo_submission_seeded", context_data={"label": label, "actor_role": "system", "insurance_company": company.name, "assigned_underwriter": underwriter.name}, timestamp=created_at))
            if status != "draft":
                db.add(AuditRecord(submission_id=submission.id, action="status_change_to_under_review" if status == "under_review" else f"status_change_to_{status}", context_data={"actor_role": "customer" if status == "under_review" else "underwriter"}, timestamp=created_at + timedelta(minutes=5)))
            if status == "info_requested":
                db.add(UnderwritingIssue(submission_id=submission.id, issue_type="MISSING_INFORMATION", description="Additional information is needed", status="open", details={"reason": "The underwriter needs further information before completing the assessment.", "recommended_action": "Provide the requested information and resubmit the application.", "severity": "MEDIUM", "sources": ["answer"]}))
        db.commit()
    except Exception:
        db.rollback(); raise
    finally:
        if own_session: db.close()


if __name__ == "__main__":
    seed()
    print(f"Seeded {len(CATALOG)} prototype products, {len(DEMO_COMPANIES)} demonstration insurers, {len(DEMO_UNDERWRITERS)} underwriters, {len(DEMO_CUSTOMERS)} customers and {len(DEMO_SUBMISSIONS)} mapped submissions.")
