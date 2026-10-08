from pydantic import BaseModel
from typing import List, Optional
from app.db.models import JobStatus

class JobListIn(BaseModel):
    id: int
    status: JobStatus
    course_name: str
    created_at: str

class JobDetailOut(BaseModel):
    id: int
    status: JobStatus
    course_name: str
    issuer_name: str
    issue_date: str
    total: int
    succeeded: int
    failed: int
    invalid: int
    processed: int
    percent_complete: float
    created_at: str
    download_url: Optional[str] = None

class JobFailureOut(BaseModel):
    certificate_id: int
    recipient_name: str
    error_type: Optional[str]
    error_message: Optional[str]

class ValidationErrorOut(BaseModel):
    row_index: int
    field: str
    message: str
    raw_value: Optional[str]

class JobFailuresOut(BaseModel):
    certificate_failures: List[JobFailureOut]
    validation_errors: List[ValidationErrorOut]
