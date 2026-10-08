from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import zipfile
import io
import csv
from pathlib import Path

from app.db.session import get_db
from app.db.models import Job, Certificate, JobStatus, CertificateStatus
from app.storage.deps import get_storage
from app.storage.base import StorageBackend

router = APIRouter()

@router.get("/jobs/{job_id}/certificates")
async def list_certificates(
    job_id: int,
    status: Optional[CertificateStatus] = None,
    page: int = 1,
    size: int = 50,
    db: Session = Depends(get_db)
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    query = db.query(Certificate).filter(Certificate.job_id == job_id)
    if status:
        query = query.filter(Certificate.status == status)

    total = query.count()
    certs = query.offset((page - 1) * size).limit(size).all()

    return {
        "total": total,
        "page": page,
        "size": size,
        "certificates": [
            {
                "id": c.id,
                "recipient_name": c.recipient_name,
                "status": c.status.value,
                "certificate_code": c.certificate_code,
                "download_url": f"/api/v1/certificates/{c.id}/download"
            } for c in certs
        ]
    }

@router.get("/certificates/{cert_id}/download")
async def download_certificate(
    cert_id: int,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage)
):
    cert = db.get(Certificate, cert_id)
    if not cert or not cert.storage_path:
        raise HTTPException(status_code=404, detail="Certificate not found or not generated")

    try:
        content = storage.open(cert.storage_path)
        filename = f"{cert.certificate_code}.pdf"

        return Response(
            content=content,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"'
            }
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="PDF file not found in storage")

@router.get("/jobs/{job_id}/download")
async def download_job_zip(
    job_id: int,
    db: Session = Depends(get_db),
    storage: StorageBackend = Depends(get_storage)
):
    job = db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status == JobStatus.PROCESSING:
        raise HTTPException(
            status_code=409,
            detail="Job is still processing. Please wait until it is completed."
        )

    def zip_generator():
        # Use a buffer for the ZIP
        zip_buffer = io.BytesIO()

        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            # 1. Create Manifest
            manifest_buffer = io.StringIO()
            writer = csv.writer(manifest_buffer)
            writer.writerow(["Recipient", "Code", "Status"])

            certs = db.query(Certificate).filter_by(job_id=job_id).all()
            for c in certs:
                writer.writerow([c.recipient_name, c.certificate_code, c.status.value])

                # 2. Add PDF if successful
                if c.status == CertificateStatus.SUCCESS and c.storage_path:
                    try:
                        content = storage.open(c.storage_path)
                        zf.writestr(f"certificates/{c.certificate_code}.pdf", content)
                    except Exception:
                        pass # Log error in prod

            zf.writestr("manifest.csv", manifest_buffer.getvalue())

        zip_buffer.seek(0)
        # We yield the buffer content in chunks to be a true stream
        while chunk := zip_buffer.read(8192):
            yield chunk

    filename = f"job_{job_id}_certificates.zip"
    return StreamingResponse(
        zip_generator(),
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
