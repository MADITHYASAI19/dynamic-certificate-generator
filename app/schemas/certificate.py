from pydantic import BaseModel, EmailStr, Field, ConfigDict
from typing import Optional, Dict, Any, List

class RecipientIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr
    course_name: Optional[str] = None
    issue_date: Optional[str] = None
    extra: Optional[Dict[str, Any]] = None

class JobCreateIn(BaseModel):
    course_name: str = Field(..., min_length=1)
    issuer_name: str = Field(..., min_length=1)
    issue_date: str = Field(..., min_length=1)
    recipients: List[RecipientIn] = Field(..., min_length=1)
    callback_url: Optional[str] = None
