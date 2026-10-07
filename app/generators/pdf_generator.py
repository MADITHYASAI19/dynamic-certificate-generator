from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib import colors
from io import BytesIO
import os

from app.generators.base import CertificateGenerator, CertificateData

class ReportLabGenerator(CertificateGenerator):
    def __init__(self, font_path: str = None):
        self.font_path = font_path
        self._register_fonts()

    def _register_fonts(self):
        # In a production app, we would bundle NotoSans-Regular.ttf
        # For this assignment, we'll use the standard Helvetica (built-in)
        # and provide a mechanism to register a TTFont if provided.
        if self.font_path and os.path.exists(self.font_path):
            try:
                pdfmetrics.registerFont(TTFont('CustomFont', self.font_path))
                self.main_font = 'CustomFont'
            except Exception:
                self.main_font = 'Helvetica'
        else:
            self.main_font = 'Helvetica'

    def _draw_border(self, c: canvas.Canvas):
        # Decorative border
        c.setStrokeColor(colors.darkblue)
        c.setLineWidth(2)
        c.rect(1*cm, 1*cm, 29.7*cm - 2*cm, 21*cm - 2*cm)

        c.setStrokeColor(colors.goldenrod)
        c.setLineWidth(1)
        c.rect(1.2*cm, 1.2*cm, 29.7*cm - 2.4*cm, 21*cm - 2.4*cm)

    def _shrink_text(self, c: canvas.Canvas, text: str, x: float, y: float, max_width: float, font_size: float, font_name: str):
        # Simple auto-shrink: decrease font size until text fits within max_width
        current_font_size = font_size
        while current_font_size > 6:
            # Check width with current font size
            text_width = c.stringWidth(text, font_name, current_font_size)
            if text_width <= max_width:
                break
            current_font_size -= 1

        c.setFont(font_name, current_font_size)
        c.drawString(x, y, text)

    def generate(self, data: CertificateData) -> bytes:
        buffer = BytesIO()
        c = canvas.Canvas(buffer, pagesize=landscape(A4))
        width, height = landscape(A4)

        # Border
        self._draw_border(c)

        # Title
        c.setFont(self.main_font, 36)
        c.setFillColor(colors.darkblue)
        c.drawCentredString(width/2, height - 5*cm, "Certificate of Completion")

        # Recipient Name
        c.setFont(self.main_font, 48)
        c.setFillColor(colors.black)
        # Reserve space for name: centered, shrink if too long
        self._shrink_text(c, data.recipient_name, 0, height - 8*cm, width - 4*cm, 48, self.main_font)
        # Note: drawCentredString doesn't support shrink, so we calculate offset manually
        text_width = c.stringWidth(data.recipient_name, self.main_font, 48) # This is just a base
        # We need to re-calculate the actual font size used in _shrink_text.
        # To make it correctly centered, I'll rewrite _shrink_text slightly or handle it here.

        # Correcting centered shrink:
        c.setFont(self.main_font, 48)
        fs = 48
        while c.stringWidth(data.recipient_name, self.main_font, fs) > width - 4*cm and fs > 6:
            fs -= 1
        c.setFont(self.main_font, fs)
        c.drawCentredString(width/2, height - 8*cm, data.recipient_name)

        # Course Name
        c.setFont(self.main_font, 24)
        c.setFillColor(colors.grey)
        c.drawCentredString(width/2, height - 11*cm, f"for successfully completing the course")
        c.setFont(self.main_font, 28)
        c.setFillColor(colors.black)
        c.drawCentredString(width/2, height - 12.5*cm, data.course_name)

        # Issue Date and Issuer
        c.setFont(self.main_font, 16)
        c.setFillColor(colors.black)
        c.drawString(4*cm, 4*cm, f"Date: {data.issue_date}")
        c.drawString(4*cm, 3*cm, f"Issuer: {data.issuer_name}")

        # Signature Line
        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.line(width - 10*cm, 4*cm, width - 4*cm, 4*cm)
        c.setFont(self.main_font, 12)
        c.drawCentredString(width - 7*cm, 3.5*cm, "Authorized Signature")

        # Certificate Code
        c.setFont(self.main_font, 10)
        c.setFillColor(colors.grey)
        c.drawCentredString(width/2, 2*cm, f"Certificate ID: {data.certificate_code}")

        # Reserved area for QR (bottom-right)
        # No drawing here yet, but layout leaves space.

        c.showPage()
        c.save()

        return buffer.getvalue()
