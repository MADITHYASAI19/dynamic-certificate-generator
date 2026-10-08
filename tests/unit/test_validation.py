import pytest
from datetime import date
from app.services.validation import ValidationService
from app.schemas.certificate import JobCreateIn
from app.core.exceptions import RequestTooLargeError
from pydantic import ValidationError

def test_validation_mixed_rows():
    service = ValidationService()
    job_date = date(2023, 10, 1)
    raw_recipients = [
        {"name": "John Doe", "email": "john@example.com"}, # Good
        {"name": "123", "email": "bad@example.com"},        # Bad name
        {"name": "Jane Doe", "email": "not-an-email"},    # Bad email
    ]

    result = service.validate_recipients(raw_recipients, job_date)

    assert result.accepted_count == 1
    assert result.rejected_count == 2
    assert len(result.valid) == 1
    assert result.valid[0].name == "John Doe"
    assert len(result.errors) == 2
    assert any(e["field"] == "name" for e in result.errors)
    assert any("email" in e["field"] for e in result.errors)

def test_job_create_empty_recipients():
    with pytest.raises(ValidationError):
        JobCreateIn(
            course_name="Python 101",
            issuer_name="Cert Org",
            issue_date=date(2023, 10, 1),
            recipients=[]
        )

def test_too_many_recipients_error():
    service = ValidationService()
    job_date = date(2023, 10, 1)
    # Create a list slightly over the limit
    from app.core.config import settings
    raw_recipients = [{"name": "Test", "email": "test@test.com"}] * (settings.MAX_RECIPIENTS_PER_JOB + 1)

    with pytest.raises(RequestTooLargeError) as excinfo:
        service.validate_recipients(raw_recipients, job_date)
    assert excinfo.value.limit == settings.MAX_RECIPIENTS_PER_JOB

def test_bad_date_range():
    service = ValidationService()
    job_date = date(2023, 10, 1)
    raw_recipients = [
        {"name": "Old Person", "email": "old@ex.com", "issue_date": "1980-01-01"}, # Too old
    ]
    result = service.validate_recipients(raw_recipients, job_date)
    assert result.rejected_count == 1
    assert "sane range" in result.errors[0]["message"]

def test_control_chars_sanitization():
    service = ValidationService()
    job_date = date(2023, 10, 1)
    raw_recipients = [
        {"name": "John\x00 Doe\n", "email": "john@example.com"},
    ]
    result = service.validate_recipients(raw_recipients, job_date)
    assert result.accepted_count == 1
    assert result.valid[0].name == "John Doe"
