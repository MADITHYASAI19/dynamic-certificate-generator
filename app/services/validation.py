import re
from typing import List, Dict, Any
from dataclasses import dataclass, field
from datetime import date, timedelta
from pydantic import ValidationError, TypeAdapter
from app.schemas.certificate import RecipientIn
from app.core.config import settings
from app.core.exceptions import RequestTooLargeError

@dataclass
class ValidationResult:
    valid: List[RecipientIn] = field(default_factory=list)
    errors: List[Dict[str, Any]] = field(default_factory=list)
    accepted_count: int = 0
    rejected_count: int = 0

def sanitize_string(value: str) -> str:
    """
    Strip control characters, collapse whitespace, and trim.
    """
    if not value:
        return value
    # Remove control characters
    value = re.sub(r'[\x00-\x1F\x7F]', '', value)
    # Collapse multiple whitespaces to one
    value = re.sub(r'\s+', ' ', value).strip()
    return value

def is_valid_name(name: str) -> bool:
    """
    Reject names that are only symbols or digits.
    """
    if not name:
        return False
    # Must contain at least one letter (any language)
    return any(char.isalpha() for char in name)

def validate_date_range(d: date) -> bool:
    """
    Sane date range: not before 1990, not more than 1 day in the future.
    """
    min_date = date(1990, 1, 1)
    max_date = date.today() + timedelta(days=1)
    return min_date <= d <= max_date

class ValidationService:
    def __init__(self):
        self.recipient_adapter = TypeAdapter(RecipientIn)

    def validate_recipients(self, raw_recipients: List[Dict[str, Any]], job_issue_date: date) -> ValidationResult:
        """
        Validates a list of raw recipient dictionaries.
        Returns a ValidationResult object containing valid recipients and per-row errors.
        """
        result = ValidationResult()

        if len(raw_recipients) > settings.MAX_RECIPIENTS_PER_JOB:
            raise RequestTooLargeError(settings.MAX_RECIPIENTS_PER_JOB)

        for index, raw_data in enumerate(raw_recipients):
            try:
                # 1. Basic Sanitization
                sanitized_data = {}
                for key, value in raw_data.items():
                    if isinstance(value, str):
                        sanitized_data[key] = sanitize_string(value)
                    else:
                        sanitized_data[key] = value

                # 2. Name Logic Check
                if "name" in sanitized_data:
                    name = sanitized_data["name"]
                    if not is_valid_name(name):
                        result.errors.append({
                            "row_index": index,
                            "field": "name",
                            "message": "Name must contain at least one letter",
                            "raw_value": raw_data.get("name")
                        })
                        result.rejected_count += 1
                        continue

                # 3. Date Validation (Override logic)
                # If issue_date is provided as a string or date, validate it
                raw_date = sanitized_data.get("issue_date")
                if raw_date:
                    try:
                        # Pydantic RecipientIn handles the cast to date,
                        # but we do a custom range check here or let the model handle it.
                        # To maintain "clear error message", we check manually before Pydantic.
                        import dateutil.parser
                        parsed_date = dateutil.parser.parse(str(raw_date)).date()
                        if not validate_date_range(parsed_date):
                            raise ValueError("Issue date must be between 1990 and tomorrow")
                        sanitized_data["issue_date"] = parsed_date
                    except Exception:
                        result.errors.append({
                            "row_index": index,
                            "field": "issue_date",
                            "message": "Invalid date format or out of sane range (1990 - tomorrow)",
                            "raw_value": raw_date
                        })
                        result.rejected_count += 1
                        continue

                # 4. Pydantic Validation
                recipient = self.recipient_adapter.validate_python(sanitized_data)
                result.valid.append(recipient)
                result.accepted_count += 1

            except ValidationError as e:
                for error in e.errors():
                    field_name = ".".join(str(loc) for loc in error["loc"])
                    result.errors.append({
                        "row_index": index,
                        "field": field_name,
                        "message": error["msg"],
                        "raw_value": raw_data.get(field_name) if isinstance(field_name, str) else "Complex object"
                    })
                result.rejected_count += 1
            except Exception as e:
                result.errors.append({
                    "row_index": index,
                    "field": "general",
                    "message": str(e),
                    "raw_value": None
                })
                result.rejected_count += 1

        return result
