from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.storage.deps import get_storage
from app.services.job_service import JobService
from app.schemas.certificate import JobCreateIn
from app.db.models import Job

router = APIRouter()

@router.post("/jobs", status_code=status.HTTP_202_ACCEPTED)
async def create_job(
    payload: JobCreateIn,
    db: Session = Depends(get_db),
    storage = Depends(get_storage)
):
    service = JobService(db, storage)

    # 1. Create and Validate (Persists to DB)
    job, validation_errors = service.create_job(payload.model_dump(), [rec.model_dump() for rec in payload.recipients])

    # 2. Enqueue Background Processing
    from app.workers.tasks import process_job
    process_job.delay(job.id)

    return {
        "job_id": job.id,
        "status": job.status.value,
        "accepted": len(job.certificates),
        "rejected": len(validation_errors),
        "validation_errors": validation_errors,
        "status_url": f"/api/v1/jobs/{job.id}/status"
    }
