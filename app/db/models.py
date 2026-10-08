import enum
from datetime import datetime, timezone, date
from typing import Optional, List
from uuid import UUID, uuid4

from sqlalchemy import (
    String, DateTime, ForeignKey, JSON, Enum, Date,
    Index, UniqueConstraint, func, text
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass

class JobStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class CertificateStatus(enum.Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255))
    api_key_hash: Mapped[str] = mapped_column(String(255), unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    jobs: Mapped[List["Job"]] = relationship(back_populates="client")
    templates: Mapped[List["Template"]] = relationship(back_populates="client")
    certificates: Mapped[List["Certificate"]] = relationship(back_populates="client")

class Template(Base):
    __tablename__ = "templates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("clients.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(default=1)
    spec: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    client: Mapped[Optional["Client"]] = relationship(back_populates="templates")

    __table_args__ = (
        UniqueConstraint("client_id", "name", "version", name="uq_client_template_version"),
    )

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"))
    template_id: Mapped[Optional[UUID]] = mapped_column(ForeignKey("templates.id"), nullable=True)
    template_version: Mapped[Optional[int]] = mapped_column(nullable=True)
    course_name: Mapped[str] = mapped_column(String(255))
    issuer_name: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[date] = mapped_column(Date)
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.PENDING)
    total: Mapped[int] = mapped_column(default=0)
    succeeded: Mapped[int] = mapped_column(default=0)
    failed: Mapped[int] = mapped_column(default=0)
    invalid: Mapped[int] = mapped_column(default=0)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    input_hash: Mapped[str] = mapped_column(String(64))
    callback_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    risk_flags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped["Client"] = relationship(back_populates="jobs")
    certificates: Mapped[List["Certificate"]] = relationship(back_populates="job")
    validation_errors: Mapped[List["ValidationError"]] = relationship(back_populates="job")

    __table_args__ = (
        UniqueConstraint("client_id", "idempotency_key", name="uq_client_idempotency"),
        Index("ix_jobs_client_created", "client_id", "created_at"),
    )

class Certificate(Base):
    __tablename__ = "certificates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"))
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    certificate_code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    recipient_name: Mapped[str] = mapped_column(String(255))
    recipient_email: Mapped[str] = mapped_column(String(255))
    course_name: Mapped[str] = mapped_column(String(255))
    issuer_name: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[date] = mapped_column(Date)
    extra: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[CertificateStatus] = mapped_column(Enum(CertificateStatus), default=CertificateStatus.PENDING)
    error_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    storage_key: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    signature: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    attempts: Mapped[int] = mapped_column(default=0)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    email_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    generated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped["Client"] = relationship(back_populates="certificates")
    job: Mapped["Job"] = relationship(back_populates="certificates")

    __table_args__ = (
        Index("ix_certs_job_status", "job_id", "status"),
        Index("ix_certs_client_created", "client_id", "created_at"),
        Index("ix_certs_code", "certificate_code"),
    )

class ValidationError(Base):
    __tablename__ = "validation_errors"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"))
    row_index: Mapped[int] = mapped_column()
    field: Mapped[str] = mapped_column(String(100))
    message: Mapped[str] = mapped_column(String(512))
    raw_value: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    job: Mapped["Job"] = relationship(back_populates="validation_errors")

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    client_id: Mapped[UUID] = mapped_column(ForeignKey("clients.id"))
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_id: Mapped[str] = mapped_column(String(255))
    meta: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
