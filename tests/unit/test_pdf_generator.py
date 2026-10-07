import pytest
from app.generators.base import CertificateData
from app.generators.pdf_generator import ReportLabGenerator
from pypdf import PdfReader
import io

@pytest.fixture
def generator():
    return ReportLabGenerator()

def test_generate_valid_pdf(generator):
    data = CertificateData(
        recipient_name="Test User",
        course_name="Test Course",
        issue_date="2026-10-07",
        issuer_name="Test Issuer",
        certificate_code="CODE123"
    )
    pdf_bytes = generator.generate(data)

    # Valid non-empty PDF
    assert len(pdf_bytes) > 0
    assert pdf_bytes.startswith(b"%PDF")

def test_pdf_contains_recipient_name(generator):
    name = "Unique Recipient Name"
    data = CertificateData(
        recipient_name=name,
        course_name="Test Course",
        issue_date="2026-10-07",
        issuer_name="Test Issuer",
        certificate_code="CODE123"
    )
    pdf_bytes = generator.generate(data)

    # Extract text using pypdf
    reader = PdfReader(io.BytesIO(pdf_bytes))
    page = reader.pages[0]
    text = page.extract_text()

    assert name in text

def test_long_name_no_overflow(generator):
    # A very long name (100 chars)
    long_name = "A" * 100
    data = CertificateData(
        recipient_name=long_name,
        course_name="Test Course",
        issue_date="2026-10-07",
        issuer_name="Test Issuer",
        certificate_code="CODE123"
    )
    # This test mainly checks that it doesn't crash and generates a PDF.
    # Visual verification is done via demo.pdf, but we check the result is valid.
    pdf_bytes = generator.generate(data)
    assert pdf_bytes.startswith(b"%PDF")
