from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.db.session import get_db
from app.db.models import Job, Certificate, ValidationError, JobStatus, CertificateStatus
from app.schemas.job_status import JobDetailOut, JobListIn, JobFailuresOut, JobFailureOut, ValidationErrorOut
from app.schemas.common import PaginationResponse

router = APIRouter()

@router.get("/jobs", response_model=PaginationResponse[JobListIn])
async def list_jobs(
    status: Optional[JobStatus] = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db)
):
    query = db.query(Job)
    if status:
        query = query.filter(Job.status == status)

    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()

    return {
        "page": page,
        "page_size": size,
        "total": total,
        "items": [
            JobListIn(
                id=j.id,
                status=j.status,
                course_name=j.course_name,
                created_at=j.created_at.isoformat()
            ) for j in items
        ]
    }

@router.get("/jobs/{job_id}", response_model=JobDetailOut)
async def get_job_status(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Calculate metrics
    total_recipients = len(job.certificates) + len(job.validation_errors)
    invalid = len(job.validation_errors)
    processed = job.succeeded + job.failed

    percent_complete = 0.0
    if total_recipients > 0:
        percent_complete = (processed / total_recipients) * 100

    download_url = None
    if job.status in [JobStatus.COMPLETED, JobStatus.COMPLETED_WITH_ERRORS]:
        download_url = f"/api/v1/jobs/{job.id}/download"

    return JobDetailOut(
        id=job.id,
        status=job.status,
        course_name=job.course_name,
        issuer_name=job.issuer_name,
        issue_date=job.issue_date,
        total=total_recipients,
        succeeded=job.succeeded,
        failed=job.failed,
        invalid=invalid,
        processed=processed,
        percent_complete=round(percent_complete, 2),
        created_at=job.created_at.isoformat(),
        download_url=download_url
    )

@router.get("/jobs/{job_id}/failures", response_model=JobFailuresOut)
async def get_job_failures(job_id: int, db: Session = Depends(get_db)):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    cert_failures = [
        JobFailureOut(
            certificate_id=c.id,
            recipient_name=c.recipient_name,
            error_type=c.error_type,
            error_message=c.error_message
        ) for c in job.certificates if c.status == CertificateStatus.FAILED
    ]

    val_errors = [
        ValidationErrorOut(
            row_index=ve.row_index,
            field=ve.field,
            message=ve.message,
            raw_value=ve.raw_value
        ) for ve in job.validation_errors
    ]

    return JobFailuresOut(
        certificate_failures=cert_failures,
        validation_errors=val_errors
    )
