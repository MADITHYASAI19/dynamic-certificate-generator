import re
from typing import List, Tuple, Dict, Any
from pydantic import ValidationError
from app.schemas.certificate import RecipientIn
from app.core.config import settings

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

class ValidationService:
    def validate_recipients(self, raw_recipients: List[Dict[str, Any]]) -> Tuple[List[RecipientIn], List[Dict[str, Any]]]:
        """
        Validates a list of raw recipient dictionaries.
        Returns a tuple of (valid_recipients, errors).
        """
        valid_recipients = []
        errors = []

        # Guard: Too many recipients (structural check)
        if len(raw_recipients) > settings.MAX_RECIPIENTS_PER_JOB:
            # This is handled at the JobCreateIn level usually, but we keep it here for safety
            raise ValueError(f"Maximum recipients per job is {settings.MAX_RECIPIENTS_PER_JOB}")

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
                        errors.append({
                            "row_index": index,
                            "field": "name",
                            "message": "Name must contain at least one letter",
                            "raw_value": raw_data.get("name")
                        })
                        continue

                # 3. Pydantic Validation
                recipient = RecipientIn(**sanitized_data)
                valid_recipients.append(recipient)

            except ValidationError as e:
                # Map Pydantic errors to the required format
                for error in e.errors():
                    field = ".".join(str(loc) for loc in error["loc"])
                    errors.append({
                        "row_index": index,
                        "field": field,
                        "message": error["msg"],
                        "raw_value": raw_data.get(field) if isinstance(field, str) else "Complex object"
                    })
            except Exception as e:
                errors.append({
                    "row_index": index,
                    "field": "general",
                    "message": str(e),
                    "raw_value": None
                })

        return valid_recipients, errors
