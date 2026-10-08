import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.models import Base, Client, Certificate, Job
from uuid import uuid4
from datetime import date

@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_client_creation(db_session):
    client = Client(name="Test Corp", api_key_hash="hashed_key")
    db_session.add(client)
    db_session.commit()
    assert client.id is not None

def test_certificate_code_unique(db_session):
    client = Client(name="Test Corp", api_key_hash="hashed_key")
    db_session.add(client)
    db_session.commit()

    job = Job(
        client_id=client.id,
        course_name="Test Course",
        issuer_name="Issuer",
        issue_date=date(2023,1,1),
        input_hash="abc"
    )
    db_session.add(job)
    db_session.commit()

    cert1 = Certificate(
        client_id=client.id,
        job_id=job.id,
        certificate_code="CERT-1",
        recipient_name="User 1",
        recipient_email="u1@ex.com",
        course_name="Test Course",
        issuer_name="Issuer",
        issue_date=date(2023,1,1),
        status="PENDING"
    )
    db_session.add(cert1)
    db_session.commit()

    cert2 = Certificate(
        client_id=client.id,
        job_id=job.id,
        certificate_code="CERT-1", # Duplicate
        recipient_name="User 2",
        recipient_email="u2@ex.com",
        course_name="Test Course",
        issuer_name="Issuer",
        issue_date=date(2023,1,1),
        status="PENDING"
    )
    db_session.add(cert2)
    with pytest.raises(Exception): # SQLAlchemy integrity error
        db_session.commit()
