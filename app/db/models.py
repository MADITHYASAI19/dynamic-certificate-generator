from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Enum
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class JobStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"

class CertificateStatus(enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    course_name = Column(String, nullable=False)
    issuer_name = Column(String, nullable=False)
    issue_date = Column(String, nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    created_at = Column(DateTime, default=datetime.utcnow)

    certificates = relationship("Certificate", back_populates="job")
    validation_errors = relationship("ValidationError", back_populates="job")

class Certificate(Base):
    __tablename__ = "certificates"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    recipient_name = Column(String, nullable=False)
    email = Column(String, nullable=False)
    certificate_code = Column(String, unique=True, index=True)
    status = Column(Enum(CertificateStatus), default=CertificateStatus.PENDING)
    storage_path = Column(String, nullable=True)
    error_type = Column(String, nullable=True)
    error_message = Column(String, nullable=True)

    job = relationship("Job", back_populates="certificates")

class ValidationError(Base):
    __tablename__ = "validation_errors"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("jobs.id"), nullable=False)
    row_index = Column(Integer, nullable=False)
    field = Column(String, nullable=False)
    message = Column(String, nullable=False)
    raw_value = Column(String, nullable=True)

    job = relationship("Job", back_populates="validation_errors")
