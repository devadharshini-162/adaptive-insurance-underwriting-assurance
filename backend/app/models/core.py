from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Text, JSON, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.base import Base

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    role = Column(String, default="agent") # agent or underwriter
    submissions = relationship("Submission", back_populates="user")

class InsuranceProduct(Base):
    __tablename__ = "insurance_products"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    description = Column(String)
    
    requirements = relationship("Requirement", back_populates="product")
    questions = relationship("Question", back_populates="product")
    submissions = relationship("Submission", back_populates="product")

class Requirement(Base):
    __tablename__ = "requirements"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("insurance_products.id"))
    name = Column(String)
    description = Column(String)
    rule_logic = Column(JSON, nullable=True)
    
    product = relationship("InsuranceProduct", back_populates="requirements")
    documents = relationship("Document", back_populates="requirement")

class Question(Base):
    __tablename__ = "questions"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("insurance_products.id"))
    text = Column(String)
    field_type = Column(String)
    is_required = Column(Boolean, default=True)
    
    product = relationship("InsuranceProduct", back_populates="questions")
    answers = relationship("Answer", back_populates="question")

class Submission(Base):
    __tablename__ = "submissions"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    product_id = Column(Integer, ForeignKey("insurance_products.id"))
    status = Column(String, default="draft")
    created_at = Column(DateTime, default=datetime.utcnow)
    
    user = relationship("User", back_populates="submissions")
    product = relationship("InsuranceProduct", back_populates="submissions")
    answers = relationship("Answer", back_populates="submission")
    documents = relationship("Document", back_populates="submission")
    evidence = relationship("Evidence", back_populates="submission")
    consistency_checks = relationship("ConsistencyCheck", back_populates="submission")
    issues = relationship("UnderwritingIssue", back_populates="submission")
    audits = relationship("AuditRecord", back_populates="submission")

class Answer(Base):
    __tablename__ = "answers"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    question_id = Column(Integer, ForeignKey("questions.id"))
    value = Column(String)
    
    submission = relationship("Submission", back_populates="answers")
    question = relationship("Question", back_populates="answers")

class Document(Base):
    __tablename__ = "documents"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    requirement_id = Column(Integer, ForeignKey("requirements.id"), nullable=True)
    file_path = Column(String)
    status = Column(String, default="uploaded")
    
    submission = relationship("Submission", back_populates="documents")
    requirement = relationship("Requirement", back_populates="documents")
    extracted_fields = relationship("ExtractedField", back_populates="document")

class ExtractedField(Base):
    __tablename__ = "extracted_fields"
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"))
    key = Column(String)
    raw_value = Column(String)
    normalized_value = Column(String, nullable=True)
    
    document = relationship("Document", back_populates="extracted_fields")
    evidences = relationship("Evidence", back_populates="extracted_field")

class Evidence(Base):
    __tablename__ = "evidence"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    extracted_field_id = Column(Integer, ForeignKey("extracted_fields.id"))
    canonical_key = Column(String)
    
    submission = relationship("Submission", back_populates="evidence")
    extracted_field = relationship("ExtractedField", back_populates="evidences")

class ConsistencyCheck(Base):
    __tablename__ = "consistency_checks"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    status = Column(String) # valid, mismatch, missing
    details = Column(JSON, nullable=True)
    
    submission = relationship("Submission", back_populates="consistency_checks")
    issues = relationship("UnderwritingIssue", back_populates="consistency_check")

class UnderwritingIssue(Base):
    __tablename__ = "underwriting_issues"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    consistency_check_id = Column(Integer, ForeignKey("consistency_checks.id"), nullable=True)
    issue_type = Column(String)
    description = Column(String)
    status = Column(String, default="open")
    details = Column(JSON, nullable=True)
    
    submission = relationship("Submission", back_populates="issues")
    consistency_check = relationship("ConsistencyCheck", back_populates="issues")

class AuditRecord(Base):
    __tablename__ = "audit_records"
    id = Column(Integer, primary_key=True, index=True)
    submission_id = Column(Integer, ForeignKey("submissions.id"))
    action = Column(String)
    context_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    submission = relationship("Submission", back_populates="audits")
