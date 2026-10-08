import re
from typing import Any, Dict
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import landscape, A4
from reportlab.graphics.barcode import qr

from app.templates_engine.schema import Page, TextEl, RectEl, LineEl, QrEl

def register_noto_fonts():
    """Register bundled Noto fonts if present."""
    try:
        # Assuming fonts are in app/assets/fonts/
        # In a real project, these would be bundled.
        # pdfmetrics.registerFont(TTFont("NotoSans", "app/assets/fonts/NotoSans-Regular.ttf"))
        pass
    except Exception:
        pass

def render_pdf(spec: Page, data: Dict[str, Any]) -> bytes:
    """
    Renders a PDF from a declarative template spec and data.
    Coordinates are in mm from top-left.
    """
    from io import BytesIO

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=(spec.width_mm * mm, spec.height_mm * mm))

    # PDF Metadata
    cert_code = data.get("certificate_code", "UNKNOWN")
    c.setTitle(cert_code)
    c.setSubject(cert_code)

    # Invert Y axis: ReportLab uses bottom-left, template uses top-left
    def transform_y(y_mm):
        return spec.height_mm * mm - (y_mm * mm)

    # Simple placeholder substitution
    def substitute(text):
        # Only allow specifically listed placeholders
        from app.templates_engine.schema import ALLOWED_PLACEHOLDERS
        for placeholder in ALLOWED_PLACEHOLDERS:
            pattern = f"\\{{\\{{ {placeholder} \\}}\\}}"
            # The spec says {{placeholder}}. The prompt says {{certificate_code}}.
            # Let's stick to {{placeholder}} style.
            text = text.replace(f"{{{{{placeholder}}}}}", str(data.get(placeholder, f"{{{placeholder}}}")))
        return text

    for el in spec.elements:
        x = el.x * mm
        y = transform_y(el.y)

        if isinstance(el, TextEl):
            text = substitute(el.content)
            c.setFont(el.font, el.size)
            c.setFillColor(HexColor(el.color))

            # Auto-shrink text to fit width
            current_size = el.size
            while current_size > el.min_size:
                c.setFont(el.font, current_size)
                w = c.stringWidth(text, el.font, current_size)
                if w <= el.max_width_mm * mm:
                    break
                current_size -= 0.5

            c.setFont(el.font, current_size)

            if el.align == "left":
                c.drawString(x, y, text)
            elif el.align == "center":
                w = c.stringWidth(text, el.font, current_size)
                c.drawString(x - w/2, y, text)
            elif el.align == "right":
                w = c.stringWidth(text, el.font, current_size)
                c.drawString(x - w, y, text)

        elif isinstance(el, RectEl):
            c.setFillColor(HexColor(el.fill) if el.fill else None)
            c.setStrokeColor(HexColor(el.stroke) if el.stroke else None)
            if el.stroke:
                c.setLineWidth(el.stroke_width * mm)

            # Rects are drawn from bottom-left in RL, but our x,y is top-left
            # We need to adjust the y to be the bottom of the rect
            rect_y = transform_y(el.y + el.height)
            c.rect(x, rect_y, el.width * mm, el.height * mm, fill=True if el.fill else False)

        elif isinstance(el, LineEl):
            c.setStrokeColor(HexColor(el.stroke))
            c.setLineWidth(el.stroke_width * mm)
            c.line(x, y, el.x2 * mm, transform_y(el.y2))

        elif isinstance(el, QrEl):
            # QR encodes verify_url
            url = data.get("verify_url", "")
            qr_code = qr.QrCode(url)
            # QR size is in pixels in RL's barcode, but we want mm.
            # Standard QR in RL: draw() takes x, y, and can be scaled.
            # We'll use the barcode generator but we need to scale it to el.size * mm.
            # Actually, RL's qr.QrCode is a graphics object.
            from reportlab.graphics import renderPDF

            # Scale factor for QR
            # The default QR is roughly 100x100 units.
            # We'll wrap it in a graphics container to control size.
            # For simplicity, we use the renderPDF helper

            # Note: Standard RL QR is a bit clunky to size in mm.
            # A better way is to use the qrcode library if available, but the prompt
            # says use ReportLab.

            # Create QR as graphics object
            qr_obj = qr.QrCode(url)
            qr_obj.width = el.size * mm
            qr_obj.height = el.size * mm

            renderPDF.draw(c, qr_obj, x, y)

    c.showPage()
    c.save()
    return buffer.getvalue()
