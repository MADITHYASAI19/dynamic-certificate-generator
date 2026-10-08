from sqlalchemy import update
from app.workers.celery_app import celery_app
from app.db.session import get_db
from app.db.models import Job, Certificate, JobStatus, CertificateStatus
from app.services.job_service import JobService
from app.storage.deps import get_storage
from app.generators.pdf_generator import ReportLabGenerator
from sqlalchemy.orm import Session

def get_db_session():
    # Celery tasks need a fresh session
    from app.db.session import AsyncSessionLocal
    return AsyncSessionLocal()

@celery_app.task(name="process_job")
def process_job(job_id: int):
    db = get_db_session()
    storage = get_storage() # Simplified for worker

    try:
        job = db.get(Job, job_id)
        if not job:
            return

        # Get all pending certificates
        pending_certs = db.query(Certificate).filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.PENDING
        ).all()

        cert_ids = [c.id for c in pending_certs]
        chunk_size = 100
        for i in range(0, len(cert_ids), chunk_size):
            chunk = cert_ids[i : i + chunk_size]
            process_chunk.delay(job_id, chunk)

        # We don't mark job as COMPLETED here because workers are still running chunks
        # The last worker to finish a chunk should theoretically finalize,
        # but better to let a separate monitor or the last chunk finalize.
        # For now, we update status to PROCESSING
        job.status = JobStatus.PROCESSING
        db.commit()

    finally:
        db.close()

@celery_app.task(name="process_chunk")
def process_chunk(job_id: int, certificate_ids: list[int]):
    db = get_db_session()
    # Use a local instance of storage and generator for the worker
    from app.storage.local import LocalStorage
    from app.core.config import settings
    storage = LocalStorage(settings.STORAGE_PATH)
    generator = ReportLabGenerator()

    try:
        job = db.get(Job, job_id)
        if not job:
            return

        for cert_id in certificate_ids:
            cert = db.get(Certificate, cert_id)
            if not cert:
                continue

            try:
                from app.generators.base import CertificateData
                cert_data = CertificateData(
                    recipient_name=cert.recipient_name,
                    course_name=job.course_name,
                    issue_date=job.issue_date,
                    issuer_name=job.issuer_name,
                    certificate_code=cert.certificate_code
                )
                pdf_bytes = generator.generate(cert_data)
                storage_key = f"jobs/{job.id}/{cert.certificate_code}.pdf"
                storage.save(storage_key, pdf_bytes)

                cert.status = CertificateStatus.SUCCESS
                cert.storage_path = storage_key

                # ATOMIC UPDATE: Increment success counter
                # Note: We'll add 'succeeded' and 'failed' columns to Job model
                db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(succeeded=Job.succeeded + 1)
                )

            except Exception as e:
                cert.status = CertificateStatus.FAILED
                cert.error_type = type(e).__name__
                cert.error_message = str(e)

                db.execute(
                    update(Job)
                    .where(Job.id == job_id)
                    .values(failed=Job.failed + 1)
                )

            db.commit()

        # FINALIZATION GUARD: Check if all certs for this job are no longer PENDING
        # This is a simple check: count remaining pending
        remaining = db.query(Certificate).filter(
            Certificate.job_id == job_id,
            Certificate.status == CertificateStatus.PENDING
        ).count()

        if remaining == 0:
            final_job = db.get(Job, job_id)
            if final_job.succeeded == 0 and final_job.failed > 0:
                final_job.status = JobStatus.FAILED
            elif final_job.failed > 0:
                final_job.status = JobStatus.COMPLETED_WITH_ERRORS
            else:
                final_job.status = JobStatus.COMPLETED
            db.commit()

    finally:
        db.close()
