import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.models import Base, Job, Certificate, JobStatus, CertificateStatus, ValidationError
from app.db.session import get_db
from app.storage.local import LocalStorage
from app.storage.deps import get_storage
import os
import shutil
import secrets

# Setup Test DB and Storage
test_db = create_engine("sqlite:///./test_status.db")
TestSessionLocal = sessionmaker(bind=test_db)
Base.metadata.create_all(test_db)

def override_get_db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()

def override_get_storage():
    return LocalStorage("./test_storage_status")

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_storage] = override_get_storage

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    try:
        if os.path.exists("./test_storage_status"):
            shutil.rmtree("./test_storage_status")
        if os.path.exists("./test_status.db"):
            os.remove("./test_status.db")
    except PermissionError:
        pass

def test_job_status_all_success():
    with TestSessionLocal() as db:
        job = Job(course_name="C", issuer_name="I", issue_date="D", status=JobStatus.COMPLETED, succeeded=10, failed=0)
        db.add(job)
        db.commit()

        for i in range(10):
            db.add(Certificate(job_id=job.id, recipient_name=f"U{i}", email=f"u{i}@e.com", certificate_code=f"S{i}_{secrets.token_hex(4)}", status=CertificateStatus.SUCCESS))
        db.commit()
        job_id = job.id

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "COMPLETED"
    assert data["total"] == 10
    assert data["succeeded"] == 10
    assert data["processed"] == 10
    assert data["percent_complete"] == 100.0
    assert data["download_url"] is not None

def test_job_status_partial_failure():
    with TestSessionLocal() as db:
        job = Job(course_name="C", issuer_name="I", issue_date="D", status=JobStatus.COMPLETED_WITH_ERRORS, succeeded=7, failed=3)
        db.add(job)
        db.commit()

        # 7 Success, 3 Failed
        for i in range(7):
            db.add(Certificate(job_id=job.id, recipient_name=f"S{i}", email=f"s{i}@e.com", certificate_code=f"S{i}_{secrets.token_hex(4)}", status=CertificateStatus.SUCCESS))
        for i in range(3):
            db.add(Certificate(job_id=job.id, recipient_name=f"F{i}", email=f"f{i}@e.com", certificate_code=f"F{i}_{secrets.token_hex(4)}", status=CertificateStatus.FAILED))

        # Add 2 validation errors
        for i in range(2):
            db.add(ValidationError(job_id=job.id, row_index=i, field="email", message="invalid", raw_value="bad"))

        db.commit()
        job_id = job.id

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 12 # 7+3+2
    assert data["succeeded"] == 7
    assert data["failed"] == 3
    assert data["invalid"] == 2
    assert data["processed"] == 10
    assert data["percent_complete"] == 83.33

def test_job_status_all_failure():
    with TestSessionLocal() as db:
        job = Job(course_name="C", issuer_name="I", issue_date="D", status=JobStatus.FAILED, succeeded=0, failed=5)
        db.add(job)
        db.commit()

        for i in range(5):
            db.add(Certificate(job_id=job.id, recipient_name=f"F{i}", email=f"f{i}@e.com", certificate_code=f"F{i}_{secrets.token_hex(4)}", status=CertificateStatus.FAILED))
        db.commit()
        job_id = job.id

    response = client.get(f"/api/v1/jobs/{job_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "FAILED"
    assert data["succeeded"] == 0
    assert data["failed"] == 5

def test_job_not_found():
    response = client.get("/api/v1/jobs/9999")
    assert response.status_code == 404
    assert "error" in response.json()
    assert response.json()["error"]["code"] == "HTTP_ERROR"
