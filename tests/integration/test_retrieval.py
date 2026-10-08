import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.main import app
from app.db.models import Base, Job, Certificate, JobStatus, CertificateStatus
from app.db.session import get_db
from app.storage.local import LocalStorage
from app.storage.deps import get_storage
import zipfile
import io
import csv
import os
import shutil

# Setup Test DB and Storage
test_db = create_engine("sqlite:///./test_retrieval.db")
TestSessionLocal = sessionmaker(bind=test_db)
Base.metadata.create_all(test_db)

def override_get_db():
    session = TestSessionLocal()
    try:
        yield session
    finally:
        session.close()

def override_get_storage():
    return LocalStorage("./test_storage")

app.dependency_overrides[get_db] = override_get_db
app.dependency_overrides[get_storage] = override_get_storage

client = TestClient(app)

@pytest.fixture(autouse=True)
def cleanup():
    yield
    try:
        if os.path.exists("./test_storage"):
            shutil.rmtree("./test_storage")
        if os.path.exists("./test_retrieval.db"):
            os.remove("./test_retrieval.db")
    except PermissionError:
        pass

def test_download_single_certificate():
    with TestSessionLocal() as db:
        job = Job(course_name="C", issuer_name="I", issue_date="D", status=JobStatus.COMPLETED)
        db.add(job)
        db.commit()

        import secrets, string
        unique_code = "".join(secrets.choice(string.ascii_uppercase) for _ in range(8))

        cert = Certificate(
            job_id=job.id,
            recipient_name="User",
            email="u@e.com",
            certificate_code=unique_code,
            status=CertificateStatus.SUCCESS,
            storage_path=f"jobs/{job.id}/{unique_code}.pdf"
        )
        db.add(cert)
        db.commit()

        os.makedirs(f"./test_storage/jobs/{job.id}", exist_ok=True)
        with open(f"./test_storage/jobs/{job.id}/{unique_code}.pdf", "wb") as f:
            f.write(b"%PDF-1.4-fake-content")

        cert_id = cert.id

    response = client.get(f"/api/v1/certificates/{cert_id}/download")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/pdf"
    assert b"fake-content" in response.content

def test_download_job_zip():
    job_id = None
    with TestSessionLocal() as db:
        job = Job(course_name="C", issuer_name="I", issue_date="D", status=JobStatus.COMPLETED)
        db.add(job)
        db.commit()
        job_id = job.id

        import secrets, string
        code1 = "".join(secrets.choice(string.ascii_uppercase) for _ in range(8))
        code2 = "".join(secrets.choice(string.ascii_uppercase) for _ in range(8))

        c1 = Certificate(job_id=job_id, recipient_name="U1", email="u1@e.com", certificate_code=code1, status=CertificateStatus.SUCCESS, storage_path=f"jobs/{job_id}/{code1}.pdf")
        c2 = Certificate(job_id=job_id, recipient_name="U2", email="u2@e.com", certificate_code=code2, status=CertificateStatus.FAILED)
        db.add_all([c1, c2])
        db.commit()

        os.makedirs(f"./test_storage/jobs/{job_id}", exist_ok=True)
        with open(f"./test_storage/jobs/{job_id}/{code1}.pdf", "wb") as f:
            f.write(b"PDF_C1")

    response = client.get(f"/api/v1/jobs/{job_id}/download")
    assert response.status_code == 200
    assert response.headers["Content-Type"] == "application/zip"

    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        file_list = z.namelist()
        assert f"certificates/{code1}.pdf" in file_list
        assert "manifest.csv" in file_list

        with io.StringIO(z.read("manifest.csv").decode()) as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert rows[0] == ["Recipient", "Code", "Status"]
            assert any("U1" in row for row in rows)
            assert any("U2" in row for row in rows)

def test_download_job_processing_409():
    job_id = None
    with TestSessionLocal() as db:
        job = Job(course_name="C", issuer_name="I", issue_date="D", status=JobStatus.PROCESSING)
        db.add(job)
        db.commit()
        job_id = job.id

    response = client.get(f"/api/v1/jobs/{job_id}/download")
    assert response.status_code == 409
    assert "still processing" in response.json()["detail"]

def test_unknown_id_404():
    response = client.get("/api/v1/certificates/9999/download")
    assert response.status_code == 404
