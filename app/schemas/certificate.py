from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import Optional, Dict, Any, List
from datetime import date
from app.core.config import settings

class RecipientIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    course_name: Optional[str] = None
    issue_date: Optional[date] = None
    extra: Optional[Dict[str, Any]] = None

class JobCreateIn(BaseModel):
    course_name: str = Field(..., min_length=1)
    issuer_name: str = Field(..., min_length=1)
    issue_date: date = Field(...)
    recipients: List[Dict[str, Any]] = Field(
        ...,
        min_length=1,
        max_length=settings.MAX_RECIPIENTS_PER_JOB
    )
    callback_url: Optional[str] = None
