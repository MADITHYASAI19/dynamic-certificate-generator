import sys
from app.generators.base import CertificateData
from app.generators.pdf_generator import ReportLabGenerator

def run_demo():
    generator = ReportLabGenerator()
    data = CertificateData(
        recipient_name="Jonathan Alexander Montgomery-Smith III",
        course_name="Advanced Production-Ready Python Backend Engineering",
        issue_date="October 7, 2026",
        issuer_name="Tech Academy International",
        certificate_code="CERT-2026-ABC-123"
    )

    pdf_bytes = generator.generate(data)

    with open("sample.pdf", "wb") as f:
        f.write(pdf_bytes)

    print("Successfully generated sample.pdf")

if __name__ == "__main__":
    run_demo()
