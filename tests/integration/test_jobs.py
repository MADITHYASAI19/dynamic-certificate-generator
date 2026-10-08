import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Job, Certificate, JobStatus, CertificateStatus
from app.services.job_service import JobService
from app.storage.local import LocalStorage
from app.generators.pdf_generator import ReportLabGenerator
import os

@pytest.fixture
def db_session(tmp_path):
    # Use SQLite for integration tests
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def storage(tmp_path):
    return LocalStorage(str(tmp_path / "storage"))

@pytest.fixture
def service(db_session, storage):
    return JobService(db_session, storage)

def test_create_job_mixed_data(service):
    job_data = {
        "course_name": "Python 101",
        "issuer_name": "Academy",
        "issue_date": "2026-10-07"
    }
    recipients_raw = [
        {"name": "Valid User", "email": "valid@example.com"},
        {"name": "Invalid", "email": "bad-email"}, # Invalid email
    ]

    job, errors = service.create_job(job_data, recipients_raw)

    assert job.id is not None
    assert len(errors) == 1
    assert len(job.certificates) == 1
    assert job.certificates[0].recipient_name == "Valid User"

def test_job_processing_partial_failure(service, storage):
    # Setup job
    job_data = {"course_name": "Python", "issuer_name": "Academy", "issue_date": "2026-10-07"}
    recipients_raw = [
        {"name": "U1", "email": "u1@ex.com"},
        {"name": "U2", "email": "u2@ex.com"},
        {"name": "U3", "email": "u3@ex.com"},
    ]
    job, _ = service.create_job(job_data, recipients_raw)

    # Patch generator to fail on the 3rd call
    with patch.object(ReportLabGenerator, 'generate', side_effect=[
        b"PDF1",
        b"PDF2",
        Exception("Generation Failed!")
    ]):
        service.process_job(job.id)

    # Check final status
    service.db.refresh(job)
    assert job.status == JobStatus.COMPLETED_WITH_ERRORS

    certs = job.certificates
    assert sum(1 for c in certs if c.status == CertificateStatus.SUCCESS) == 2
    assert sum(1 for c in certs if c.status == CertificateStatus.FAILED) == 1

    # Verify PDFs were written for the first two
    assert storage.exists(f"jobs/{job.id}/{certs[0].certificate_code}.pdf")
    assert storage.exists(f"jobs/{job.id}/{certs[1].certificate_code}.pdf")
    assert not storage.exists(f"jobs/{job.id}/{certs[2].certificate_code}.pdf")
