from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class CertificateData:
    recipient_name: str
    course_name: str
    issue_date: str
    issuer_name: str
    certificate_code: str
    extra: Optional[dict] = None

class CertificateGenerator(ABC):
    @abstractmethod
    def generate(self, data: CertificateData) -> bytes:
        """Generates a certificate PDF and returns it as bytes."""
        pass
