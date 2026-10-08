import secrets
import string
from typing import Tuple
from sqlalchemy.orm import Session
from app.db.models import Job, Certificate, ValidationError, JobStatus, CertificateStatus
from app.services.validation import ValidationService
from app.generators.base import CertificateData
from app.generators.pdf_generator import ReportLabGenerator
from app.storage.base import StorageBackend

class JobService:
    def __init__(self, db: Session, storage: StorageBackend, generator=None):
        self.db = db
        self.storage = storage
        self.generator = generator or ReportLabGenerator()
        self.validator = ValidationService()

    def _generate_cert_code(self) -> str:
        """Generates a unique certificate code like CERT-2026-8F3K2A."""
        while True:
            # 6 random uppercase alphanumeric characters
            code = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
            full_code = f"CERT-2026-{code}"

            # Collision check
            exists = self.db.query(Certificate).filter_by(certificate_code=full_code).first()
            if not exists:
                return full_code

    def create_job(self, job_data: dict, recipients_raw: list) -> Tuple[Job, list]:
        """
        Step 1: Validate and Persist Job and initial records in one transaction.
        """
        # 1. Validate recipients
        valid_recipients, validation_errors = self.validator.validate_recipients(recipients_raw)

        # 2. Create Job
        job = Job(
            course_name=job_data["course_name"],
            issuer_name=job_data["issuer_name"],
            issue_date=job_data["issue_date"],
            status=JobStatus.PROCESSING
        )
        self.db.add(job)
        self.db.flush() # Get job.id

        # 3. Persist validation errors
        for err in validation_errors:
            val_err = ValidationError(
                job_id=job.id,
                row_index=err["row_index"],
                field=err["field"],
                message=err["message"],
                raw_value=str(err["raw_value"])
            )
            self.db.add(val_err)

        # 4. Persist valid certificates as PENDING
        for rec in valid_recipients:
            cert = Certificate(
                job_id=job.id,
                recipient_name=rec.name,
                email=rec.email,
                certificate_code=self._generate_cert_code(),
                status=CertificateStatus.PENDING
            )
            self.db.add(cert)

        self.db.commit()
        return job, validation_errors

    def process_job(self, job_id: int):
        """
        Step 3 & 4: Process each certificate synchronously.
        """
        job = self.db.get(Job, job_id)
        if not job:
            return

        certificates = self.db.query(Certificate).filter_by(job_id=job_id).all()
        success_count = 0
        failure_count = 0

        for cert in certificates:
            try:
                # Wrap each in its own transaction logic (simulated here by commit after each)
                cert_data = CertificateData(
                    recipient_name=cert.recipient_name,
                    course_name=job.course_name,
                    issue_date=job.issue_date,
                    issuer_name=job.issuer_name,
                    certificate_code=cert.certificate_code
                )

                pdf_bytes = self.generator.generate(cert_data)

                # Storage key: jobs/{job_id}/{certificate_code}.pdf
                storage_key = f"jobs/{job.id}/{cert.certificate_code}.pdf"
                self.storage.save(storage_key, pdf_bytes)

                cert.status = CertificateStatus.SUCCESS
                cert.storage_path = storage_key
                success_count += 1
            except Exception as e:
                cert.status = CertificateStatus.FAILED
                cert.error_type = type(e).__name__
                cert.error_message = str(e)
                failure_count += 1

            # commit each result independently so one failure doesn't roll back others
            self.db.commit()

        # Final Job Status
        if failure_count == 0:
            job.status = JobStatus.COMPLETED
        elif success_count == 0:
            job.status = JobStatus.FAILED
        else:
            job.status = JobStatus.COMPLETED_WITH_ERRORS

        self.db.commit()
        return job
