import pytest
from app.services.validation import ValidationService
from app.schemas.certificate import RecipientIn
from app.core.config import settings

@pytest.fixture
def validator():
    return ValidationService()

def test_validate_valid_row(validator):
    raw = [{"name": "John Doe", "email": "john@example.com"}]
    valid, errors = validator.validate_recipients(raw)
    assert len(valid) == 1
    assert len(errors) == 0
    assert valid[0].name == "John Doe"

def test_validate_bad_email(validator):
    raw = [{"name": "John Doe", "email": "not-an-email"}]
    valid, errors = validator.validate_recipients(raw)
    assert len(valid) == 0
    assert len(errors) == 1
    assert errors[0]["field"] == "email"

def test_validate_empty_name(validator):
    raw = [{"name": "  ", "email": "john@example.com"}]
    valid, errors = validator.validate_recipients(raw)
    assert len(valid) == 0
    assert len(errors) == 1
    # Pydantic min_length=1 handles this after strip
    assert "name" in errors[0]["field"]

def test_validate_mixed_rows(validator):
    raw = [
        {"name": "Valid User", "email": "valid@example.com"},
        {"name": "Invalid User", "email": "bad-email"},
        {"name": "", "email": "no-name@example.com"},
    ]
    valid, errors = validator.validate_recipients(raw)
    assert len(valid) == 1
    assert len(errors) == 2
    assert valid[0].name == "Valid User"

def test_validate_control_characters(validator):
    raw = [{"name": "John\x00 Doe\n\t", "email": "john@example.com"}]
    valid, errors = validator.validate_recipients(raw)
    assert len(valid) == 1
    assert valid[0].name == "John Doe"

def test_validate_name_only_symbols(validator):
    raw = [{"name": "12345 !!!", "email": "john@example.com"}]
    valid, errors = validator.validate_recipients(raw)
    assert len(valid) == 0
    assert len(errors) == 1
    assert "at least one letter" in errors[0]["message"]

def test_validate_oversize_list(validator, monkeypatch):
    # Set limit small for testing
    monkeypatch.setattr(settings, "MAX_RECIPIENTS_PER_JOB", 2)
    raw = [
        {"name": "U1", "email": "u1@ex.com"},
        {"name": "U2", "email": "u2@ex.com"},
        {"name": "U3", "email": "u3@ex.com"},
    ]
    with pytest.raises(ValueError, match="Maximum recipients"):
        validator.validate_recipients(raw)
