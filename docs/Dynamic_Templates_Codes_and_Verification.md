# Dynamic Templates, Certificate Codes & Verification/Search

An add-on to the Bulk Certificate Generator plan. It covers three things:

1. **Dynamic templates**: clients can define their own layouts, with the required static template kept as the default.
2. **A unique, typo-proof code on every certificate**.
3. **Verification and search**: anyone can verify a certificate by its code, and clients can search every certificate they issued.

> **Tested:** all code in sections 2, 3 and 4 was run before being put in this file. The code generator was checked on 20,000 codes with zero collisions, and against every possible single-character typo with zero missed. Rendering, template validation, the verify endpoint and search (including tenant isolation) all pass.

---

## 1. Why this is safe to add (the assignment says "single predefined template")

The assignment asks for **one predefined template and says you don't need a template editor**. So:

- **The static template stays the default.** Every job works with no template field at all.
- The default is written in the *same engine* as custom templates (`builtin.py`). So there is one rendering path to test, not two.
- Dynamic templates are an **optional extra**: `template_id` is an optional field on job creation.

In the README, describe it as: *"Required: one predefined template (default). Bonus: declarative JSON templates, which a client can use through an optional `template_id`."* Then you meet the requirement exactly and the extra is clearly labeled as optional.

### Key design decisions (be ready to explain these)

| Decision | Why |
|---|---|
| Templates are **pure JSON, not HTML/Jinja** | Nothing executes. Placeholders are plain text substitution, which rules out template injection (SSTI) and arbitrary file reads. |
| **Allow-lists** for fonts, placeholders and element types | The client cannot reference `{{__import__}}` or load any file. |
| Template **must contain a QR or `{{certificate_code}}`** | Every certificate stays verifiable, whatever the design. |
| **Versioned and immutable once used** | Each certificate stores `template_id` + `template_version`, so reprints and retries look identical, and editing a template creates version+1. |
| **Auto-shrink text** (`size` down to `min_size`) | Long names and courses never overflow the page. |
| Limits (60 elements, size ranges, page size bounds) | Prevents a malicious template from making a worker burn CPU or memory. |

---

## 2. Certificate codes

Format: `CERT-2026-RZSMMS4HR`, which is prefix, year, 8 random characters and 1 check character.

- **Random, not sequential**, so codes can't be guessed or enumerated (`secrets`, not `random`).
- **Crockford base32** (no `I`, `L`, `O`, `U`), so people can read a code from paper without confusion. 32^8 gives about 1.1 trillion combinations per year.
- **Check character**: a typo is rejected instantly with no database query. The weights are odd, so every single-character typo is detected (verified exhaustively).
- **Forgiving input**: lowercase, extra spaces, and `O`/`I`/`L` mixed up with `0`/`1` are all normalized.
- Still keep a `UNIQUE` index in the DB and retry on the rare collision. The code is an identifier, not a secret. Authenticity comes from the **signature** (section 4).

### `app/codes.py`
```python
"""Certificate code generation + checksum validation.

Format:  CERT-2026-7K3M9QXD4   (prefix - year - 8 random chars + 1 check char)
Alphabet is Crockford-style base32: no I, L, O, U -> no look-alike mistakes when typed by hand.
The final character is a checksum, so typos are rejected BEFORE hitting the database.
"""
import re
import secrets
from datetime import date

ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"  # 32 chars
PREFIX = "CERT"
_CODE_RE = re.compile(r"^CERT-(\d{4})-([0-9A-HJKMNP-TV-Z]{9})$")


def _checksum(body: str) -> str:
    """Weighted mod-32 checksum. Odd weights => ANY single-character typo is caught."""
    total = sum((2 * i + 1) * ALPHABET.index(c) for i, c in enumerate(body))  # odd weights are coprime with 32
    return ALPHABET[total % 32]


def generate_code(year: int | None = None) -> str:
    year = year or date.today().year
    body = "".join(secrets.choice(ALPHABET) for _ in range(8))
    return f"{PREFIX}-{year}-{body}{_checksum(body)}"


def normalize_code(raw: str) -> str:
    """Make user input forgiving: case, spaces, and look-alike characters."""
    code = raw.strip().upper().replace(" ", "")
    head, _, tail = code.rpartition("-")
    tail = tail.replace("O", "0").replace("I", "1").replace("L", "1")
    return f"{head}-{tail}" if head else code


def is_valid_format(code: str) -> bool:
    """True only if the pattern AND checksum are correct (no DB hit needed)."""
    m = _CODE_RE.match(code)
    if not m:
        return False
    body_and_check = m.group(2)
    return _checksum(body_and_check[:-1]) == body_and_check[-1]
```

---

## 3. Dynamic template engine

### Example template JSON (what a client would send)

```json
{
  "page": { "width_mm": 297, "height_mm": 210, "background_color": "#FFFDF5" },
  "elements": [
    { "type": "rect", "x_mm": 8, "y_mm": 8, "w_mm": 281, "h_mm": 194, "stroke_color": "#7A1F3D", "stroke_width": 3 },
    { "type": "text", "text": "Certificate of Achievement", "x_mm": 148.5, "y_mm": 50, "size": 34, "font": "Times-Bold", "color": "#7A1F3D" },
    { "type": "text", "text": "{{recipient_name}}", "x_mm": 148.5, "y_mm": 100, "size": 32, "min_size": 12, "max_width_mm": 230, "font": "Times-Bold" },
    { "type": "text", "text": "{{course_name}}", "x_mm": 148.5, "y_mm": 125, "size": 22, "font": "Times-Roman" },
    { "type": "qr", "x_mm": 18, "y_mm": 165, "size_mm": 26 },
    { "type": "text", "text": "ID: {{certificate_code}}", "x_mm": 148.5, "y_mm": 190, "size": 10, "font": "Courier" }
  ]
}
```

Coordinates are in **millimetres from the top-left** of the page. Available placeholders: `recipient_name`, `course_name`, `issue_date`, `issuer_name`, `certificate_code`, `achievement_text`, `grade`, `verify_url`.

### `app/template_schema.py` (validation: the security layer)
```python
"""Declarative certificate template: pure JSON, NO executable code (safe by design)."""
import re
from typing import Annotated, Literal, Union
from pydantic import BaseModel, Field, field_validator

# Only these placeholders may be used in templates.
ALLOWED_FIELDS = {
    "recipient_name", "course_name", "issue_date", "issuer_name",
    "certificate_code", "achievement_text", "grade", "verify_url",
}
ALLOWED_FONTS = {"Helvetica", "Helvetica-Bold", "Times-Roman", "Times-Bold", "Courier"}
PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class Page(BaseModel):
    width_mm: float = Field(297, ge=50, le=600)    # A4 landscape default
    height_mm: float = Field(210, ge=50, le=600)
    background_color: str = "#FFFFFF"

    @field_validator("background_color")
    @classmethod
    def _hex(cls, v):
        if not HEX_RE.match(v):
            raise ValueError("must be a hex color like #FFFFFF")
        return v


class TextEl(BaseModel):
    type: Literal["text"] = "text"
    text: str = Field(max_length=500)              # may contain {{placeholders}}
    x_mm: float
    y_mm: float                                    # from the TOP of the page
    max_width_mm: float = Field(200, gt=0)
    font: str = "Helvetica"
    size: float = Field(18, ge=6, le=120)
    min_size: float = Field(10, ge=4, le=120)      # auto-shrink floor
    color: str = "#000000"
    align: Literal["left", "center", "right"] = "center"

    @field_validator("font")
    @classmethod
    def _font(cls, v):
        if v not in ALLOWED_FONTS:
            raise ValueError(f"font must be one of {sorted(ALLOWED_FONTS)}")
        return v

    @field_validator("color")
    @classmethod
    def _color(cls, v):
        if not HEX_RE.match(v):
            raise ValueError("color must be hex like #112233")
        return v

    @field_validator("text")
    @classmethod
    def _placeholders(cls, v):
        bad = set(PLACEHOLDER_RE.findall(v)) - ALLOWED_FIELDS
        if bad:
            raise ValueError(f"unknown placeholders: {sorted(bad)}")
        return v


class RectEl(BaseModel):
    type: Literal["rect"] = "rect"
    x_mm: float
    y_mm: float
    w_mm: float = Field(gt=0)
    h_mm: float = Field(gt=0)
    stroke_color: str = "#000000"
    stroke_width: float = Field(1, ge=0, le=20)
    fill_color: str | None = None


class LineEl(BaseModel):
    type: Literal["line"] = "line"
    x1_mm: float
    y1_mm: float
    x2_mm: float
    y2_mm: float
    color: str = "#000000"
    width: float = Field(1, ge=0.1, le=20)


class QrEl(BaseModel):
    type: Literal["qr"] = "qr"
    x_mm: float
    y_mm: float
    size_mm: float = Field(25, ge=10, le=80)


Element = Annotated[Union[TextEl, RectEl, LineEl, QrEl], Field(discriminator="type")]


class TemplateSpec(BaseModel):
    page: Page = Page()
    elements: list[Element] = Field(max_length=60)

    @field_validator("elements")
    @classmethod
    def _needs_code(cls, els):
        # A template must show the certificate code or QR so it is verifiable.
        has_code = any(
            (e.type == "qr") or (e.type == "text" and "certificate_code" in e.text)
            for e in els
        )
        if not has_code:
            raise ValueError("template must include a QR element or {{certificate_code}}")
        return els
```

### `app/renderer.py` (JSON + data → PDF)
```python
"""Render a TemplateSpec + data into a PDF (bytes)."""
import io
import qrcode
from reportlab.lib.colors import HexColor
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .template_schema import PLACEHOLDER_RE, TemplateSpec, TextEl


def _fill(text: str, data: dict[str, str]) -> str:
    # Plain substitution. Never eval/format -> templates cannot execute code.
    return PLACEHOLDER_RE.sub(lambda m: str(data.get(m.group(1), "")), text)


def _fit_size(text: str, el: TextEl) -> float:
    size = el.size
    while size > el.min_size and stringWidth(text, el.font, size) > el.max_width_mm * mm:
        size -= 0.5
    return size


def _qr_image(url: str) -> ImageReader:
    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return ImageReader(buf)


def render_pdf(spec: TemplateSpec, data: dict[str, str]) -> bytes:
    pw, ph = spec.page.width_mm * mm, spec.page.height_mm * mm
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(pw, ph))
    c.setTitle(f"Certificate {data.get('certificate_code', '')}")
    c.setSubject(data.get("certificate_code", ""))

    c.setFillColor(HexColor(spec.page.background_color))
    c.rect(0, 0, pw, ph, stroke=0, fill=1)

    for el in spec.elements:
        if el.type == "rect":
            c.setStrokeColor(HexColor(el.stroke_color))
            c.setLineWidth(el.stroke_width)
            if el.fill_color:
                c.setFillColor(HexColor(el.fill_color))
            c.rect(el.x_mm * mm, ph - (el.y_mm + el.h_mm) * mm,
                   el.w_mm * mm, el.h_mm * mm,
                   stroke=1 if el.stroke_width else 0, fill=1 if el.fill_color else 0)
        elif el.type == "line":
            c.setStrokeColor(HexColor(el.color))
            c.setLineWidth(el.width)
            c.line(el.x1_mm * mm, ph - el.y1_mm * mm, el.x2_mm * mm, ph - el.y2_mm * mm)
        elif el.type == "qr":
            c.drawImage(_qr_image(data.get("verify_url", "")),
                        el.x_mm * mm, ph - (el.y_mm + el.size_mm) * mm,
                        el.size_mm * mm, el.size_mm * mm)
        elif el.type == "text":
            text = _fill(el.text, data)
            size = _fit_size(text, el)
            c.setFillColor(HexColor(el.color))
            c.setFont(el.font, size)
            x, y = el.x_mm * mm, ph - el.y_mm * mm
            {"left": c.drawString, "center": c.drawCentredString,
             "right": c.drawRightString}[el.align](x, y, text)
    c.showPage()
    c.save()
    return buf.getvalue()
```

### `app/builtin.py` (the static default, using the same engine)
```python
"""The default STATIC template, expressed with the same dynamic engine."""
from .template_schema import TemplateSpec

DEFAULT_TEMPLATE = TemplateSpec.model_validate({
    "page": {"width_mm": 297, "height_mm": 210, "background_color": "#FFFFFF"},
    "elements": [
        {"type": "rect", "x_mm": 8, "y_mm": 8, "w_mm": 281, "h_mm": 194, "stroke_color": "#1F3A5F", "stroke_width": 4},
        {"type": "rect", "x_mm": 13, "y_mm": 13, "w_mm": 271, "h_mm": 184, "stroke_color": "#C9A227", "stroke_width": 1},
        {"type": "text", "text": "Certificate of Completion", "x_mm": 148.5, "y_mm": 50, "size": 36, "font": "Times-Bold", "color": "#1F3A5F"},
        {"type": "text", "text": "This is proudly presented to", "x_mm": 148.5, "y_mm": 75, "size": 16, "font": "Times-Roman", "color": "#444444"},
        {"type": "text", "text": "{{recipient_name}}", "x_mm": 148.5, "y_mm": 98, "size": 34, "min_size": 12, "max_width_mm": 230, "font": "Times-Bold", "color": "#000000"},
        {"type": "text", "text": "for successfully completing", "x_mm": 148.5, "y_mm": 115, "size": 14, "font": "Times-Roman", "color": "#444444"},
        {"type": "text", "text": "{{course_name}}", "x_mm": 148.5, "y_mm": 130, "size": 24, "min_size": 12, "max_width_mm": 230, "font": "Times-Bold", "color": "#1F3A5F"},
        {"type": "text", "text": "{{achievement_text}}", "x_mm": 148.5, "y_mm": 143, "size": 12, "min_size": 8, "max_width_mm": 230, "font": "Times-Roman", "color": "#555555"},
        {"type": "text", "text": "Issued on {{issue_date}}", "x_mm": 55, "y_mm": 175, "align": "left", "size": 12, "font": "Helvetica", "color": "#333333"},
        {"type": "line", "x1_mm": 190, "y1_mm": 172, "x2_mm": 250, "y2_mm": 172, "color": "#333333", "width": 1},
        {"type": "text", "text": "{{issuer_name}}", "x_mm": 220, "y_mm": 178, "size": 12, "font": "Helvetica-Bold", "color": "#333333"},
        {"type": "qr", "x_mm": 18, "y_mm": 165, "size_mm": 26},
        {"type": "text", "text": "ID: {{certificate_code}}", "x_mm": 148.5, "y_mm": 190, "size": 10, "font": "Courier", "color": "#555555"},
    ],
})
```

### New/changed endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/templates` | Create a template (validated; version 1) |
| PUT | `/api/v1/templates/{id}` | Creates a **new version** (old certificates keep the old one) |
| GET | `/api/v1/templates` | List own templates plus the built-in default |
| POST | `/api/v1/templates/validate` | Check a template without saving |
| GET | `/api/v1/templates/{id}/preview` | Sample PDF with dummy data |
| POST | `/api/v1/jobs` | New **optional** field: `template_id` (omit → built-in default) |

**Later extensions:** background image upload (PNG/JPEG only, size-limited, re-encoded with Pillow to strip payloads), custom fonts for Indian scripts, and a per-recipient `template_override`.

---

## 4. Verification & search

Two different needs, so **two different endpoints with different privacy rules**:

| | Public verification | Private search |
|---|---|---|
| Who | Anyone (employer, college) | Authenticated client (API key) |
| Input | **Exact code only** | Name, email, course, code, job, status, or one `q` box |
| Output | Verification result plus masked email | Full details (own tenant only) |
| Why | Prevents scraping everyone's data | Staff need to find "that certificate for Rahul" |

> **Do not build a public name/email search.** It would let anyone enumerate your recipients' personal data, which is a privacy and legal risk. "Find everything by searching" is exactly what the private search provides, and the public side stays lookup-by-code.

### Verification result states

| Result | Meaning |
|---|---|
| `VALID` | Found, signature matches, not revoked |
| `REVOKED` | Found but revoked by the issuer (reason shown) |
| `TAMPERED` | Found, but the stored data no longer matches its signature (the DB row was altered after issuing) |
| `NOT_FOUND` | Well-formed code, but no such certificate |
| `INVALID_FORMAT` | Typo or garbage, rejected by the checksum without any DB query |

The signature is `HMAC-SHA256(SECRET_KEY, code | name | course | date | issuer)`, created when the certificate is issued and re-checked on every verification, using constant-time comparison.

### `app/models.py`
```python
import uuid
from datetime import date, datetime, timezone
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _now():
    return datetime.now(timezone.utc)


class Template(Base):
    """Versioned template. A used version is IMMUTABLE: edits create version+1."""
    __tablename__ = "templates"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str | None] = mapped_column(String, index=True)   # None = built-in/global
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, default=1)
    spec: Mapped[dict] = mapped_column(JSON)                            # validated TemplateSpec
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Certificate(Base):
    __tablename__ = "certificates"
    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    client_id: Mapped[str] = mapped_column(String, index=True)
    job_id: Mapped[str] = mapped_column(String, index=True)
    template_id: Mapped[str | None] = mapped_column(ForeignKey("templates.id"))
    template_version: Mapped[int | None] = mapped_column(Integer)       # snapshot for reproducibility
    certificate_code: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    recipient_name: Mapped[str] = mapped_column(String(100), index=True)
    recipient_email: Mapped[str] = mapped_column(String(254), index=True)
    course_name: Mapped[str] = mapped_column(String(200), index=True)
    issuer_name: Mapped[str] = mapped_column(String(100))
    issue_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="SUCCESS")
    signature: Mapped[str] = mapped_column(String(64))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoke_reason: Mapped[str | None] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    __table_args__ = (Index("ix_cert_client_created", "client_id", "created_at"),)
```

### `app/verify_service.py` (verification and search logic)
```python
import hmac, hashlib
from sqlalchemy import or_, select, func
from sqlalchemy.orm import Session
from .codes import is_valid_format, normalize_code
from .models import Certificate

SECRET_KEY = b"change-me"  # load from env in real code


def sign(code: str, name: str, course: str, issue_date: str, issuer: str) -> str:
    msg = "|".join([code, name, course, issue_date, issuer]).encode()
    return hmac.new(SECRET_KEY, msg, hashlib.sha256).hexdigest()


def mask_email(email: str) -> str:
    user, _, domain = email.partition("@")
    return f"{user[:1]}{'*' * max(len(user) - 1, 1)}@{domain}"


def mask_name(name: str) -> str:
    return " ".join(p[0] + "*" * (len(p) - 1) for p in name.split())


def verify(db: Session, raw_code: str, public: bool = True) -> dict:
    """Return a verification result. Order matters: cheap checks first."""
    code = normalize_code(raw_code)
    if not is_valid_format(code):                       # typo / garbage -> no DB hit
        return {"result": "INVALID_FORMAT", "code": code}
    cert = db.scalar(select(Certificate).where(Certificate.certificate_code == code))
    if cert is None:
        return {"result": "NOT_FOUND", "code": code}

    expected = sign(cert.certificate_code, cert.recipient_name, cert.course_name,
                    cert.issue_date.isoformat(), cert.issuer_name)
    if not hmac.compare_digest(expected, cert.signature):
        result = "TAMPERED"                              # DB row changed after issuing
    elif cert.revoked_at:
        result = "REVOKED"
    else:
        result = "VALID"

    return {
        "result": result,
        "code": cert.certificate_code,
        "recipient_name": cert.recipient_name,
        "course_name": cert.course_name,
        "issuer_name": cert.issuer_name,
        "issue_date": cert.issue_date.isoformat(),
        "template_version": cert.template_version,
        "revoked_reason": cert.revoke_reason if result == "REVOKED" else None,
        # PII: public page never shows the email
        "recipient_email": mask_email(cert.recipient_email) if public else cert.recipient_email,
    }


def search(db: Session, client_id: str, *, q: str | None = None, code: str | None = None,
           name: str | None = None, email: str | None = None, course: str | None = None,
           job_id: str | None = None, status: str | None = None,
           page: int = 1, page_size: int = 20) -> dict:
    """Authenticated search. ALWAYS scoped by client_id (tenant isolation)."""
    page_size = min(max(page_size, 1), 100)
    stmt = select(Certificate).where(Certificate.client_id == client_id)

    if q:  # one search box -> match any of the main fields
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            Certificate.certificate_code.ilike(like), Certificate.recipient_name.ilike(like),
            Certificate.recipient_email.ilike(like), Certificate.course_name.ilike(like)))
    if code:   stmt = stmt.where(Certificate.certificate_code == normalize_code(code))
    if name:   stmt = stmt.where(Certificate.recipient_name.ilike(f"%{name.strip()}%"))
    if email:  stmt = stmt.where(func.lower(Certificate.recipient_email) == email.strip().lower())
    if course: stmt = stmt.where(Certificate.course_name.ilike(f"%{course.strip()}%"))
    if job_id: stmt = stmt.where(Certificate.job_id == job_id)
    if status == "REVOKED":
        stmt = stmt.where(Certificate.revoked_at.is_not(None))
    elif status:
        stmt = stmt.where(Certificate.status == status, Certificate.revoked_at.is_(None))

    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    rows = db.scalars(stmt.order_by(Certificate.created_at.desc())
                      .offset((page - 1) * page_size).limit(page_size)).all()
    return {"page": page, "page_size": page_size, "total": total, "items": [
        {"id": r.id, "code": r.certificate_code, "recipient_name": r.recipient_name,
         "recipient_email": r.recipient_email, "course_name": r.course_name,
         "issue_date": r.issue_date.isoformat(), "job_id": r.job_id,
         "status": "REVOKED" if r.revoked_at else r.status} for r in rows]}
```

### `app/api.py` (endpoints)
```python
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from .models import Base
from .template_schema import TemplateSpec
from . import verify_service as vs

engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
Base.metadata.create_all(engine)
app = FastAPI()


def get_db():
    with SessionLocal() as s:
        yield s


def get_client_id(x_api_key: str = Header(...)) -> str:
    # Demo only: real code hashes the key and looks up the Client row.
    if not x_api_key.startswith("key-"):
        raise HTTPException(401, "invalid API key")
    return x_api_key


@app.get("/verify/{code}")                       # PUBLIC, exact code only
def verify_public(code: str, db: Session = Depends(get_db)):
    res = vs.verify(db, code, public=True)
    if res["result"] in ("NOT_FOUND", "INVALID_FORMAT"):
        raise HTTPException(404, res)
    return res


@app.get("/api/v1/certificates/search")          # PRIVATE, full search
def search_certs(q: str | None = None, code: str | None = None, name: str | None = None,
                 email: str | None = None, course: str | None = None, job_id: str | None = None,
                 status: str | None = None, page: int = Query(1, ge=1), page_size: int = 20,
                 client_id: str = Depends(get_client_id), db: Session = Depends(get_db)):
    return vs.search(db, client_id, q=q, code=code, name=name, email=email, course=course,
                     job_id=job_id, status=status, page=page, page_size=page_size)


@app.post("/api/v1/templates/validate")          # check a template without saving
def validate_template(spec: dict, _: str = Depends(get_client_id)):
    TemplateSpec.model_validate(spec)
    return {"valid": True}
```

### Example calls

```bash
# Public: verify by code (QR scan opens this)
curl https://yourapi.com/verify/CERT-2026-RZSMMS4HR
```
```json
{
  "result": "VALID",
  "code": "CERT-2026-RZSMMS4HR",
  "recipient_name": "Rahul Shah",
  "course_name": "Advanced Python Programming",
  "issuer_name": "TechClub",
  "issue_date": "2026-10-05",
  "template_version": 1,
  "revoked_reason": null,
  "recipient_email": "r****@gmail.com"
}
```

```bash
# Private: search everything you issued
curl -H "X-API-Key: key-..." "https://yourapi.com/api/v1/certificates/search?q=rahul"
curl -H "X-API-Key: key-..." "https://yourapi.com/api/v1/certificates/search?email=priya@yahoo.com"
curl -H "X-API-Key: key-..." "https://yourapi.com/api/v1/certificates/search?course=python&status=REVOKED&page=1&page_size=50"
```

### Production notes for search

- **PostgreSQL `pg_trgm` index** so `ILIKE '%rahul%'` stays fast on millions of rows:
  ```sql
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
  CREATE INDEX ix_cert_name_trgm  ON certificates USING gin (recipient_name gin_trgm_ops);
  CREATE INDEX ix_cert_email_trgm ON certificates USING gin (recipient_email gin_trgm_ops);
  CREATE INDEX ix_cert_course_trgm ON certificates USING gin (course_name gin_trgm_ops);
  ```
- Escape `%` and `_` in user-supplied search text (or use `.contains(..., autoescape=True)`).
- **Always** filter by `client_id` (tenant isolation, already tested above).
- Rate-limit the public `/verify` endpoint so codes can't be brute-forced.
- Page size is capped at 100.
- **AI upgrade (optional):** fuzzy / typo-tolerant name search (`rapidfuzz`), or embeddings for "find certificates about data science", while keeping exact filters as the base.
- Log every verification (code, result, time) to the audit table. Issuers like seeing "your certificate was verified 3 times".

---

## 5. Tests to add

| Test | Asserts |
|---|---|
| Code uniqueness | 20,000 generated codes have no duplicates |
| Checksum | Every single-character typo is rejected |
| Normalization | Lowercase, spaces and `O`/`0` mix-ups still resolve |
| Template: valid | A good template validates and renders a PDF containing the name and code |
| Template: unsafe | Unknown placeholder, unknown font, and missing code/QR are all rejected |
| Template: overflow | A 90-character name renders without error |
| Template versioning | Editing creates v2; existing certificates still render with v1 |
| Verify: valid / revoked / tampered / not found / bad format | Correct result for each |
| Verify privacy | Public response masks the email |
| Search filters | `q`, `name`, `email`, `course`, `code`, `status`, pagination |
| Tenant isolation | Client A can never find Client B's certificates |

---

## 6. Prompts to add to your build (use after Phase 7)

### Prompt A: Certificate codes
```
Add certificate code generation using the attached codes.py design: format CERT-YYYY-XXXXXXXXC (8 random Crockford base32
chars + 1 weighted check char with odd weights), generated with the secrets module. Integrate it into job processing:
generate a code per certificate, keep the UNIQUE DB constraint, and retry on the rare collision (max 5 times).
Add tests: 20k uniqueness, every single-char typo rejected, normalization of case/spaces/O-0/I-1.
```

### Prompt B: Dynamic template engine
```
Add a dynamic template system with Pydantic v2 (discriminated union of text/rect/line/qr elements), allow-lists for fonts and
placeholders, size limits, and a rule that every template must include a QR or {{certificate_code}}.
Implement render_pdf(spec, data) with ReportLab, with auto-shrinking text. Re-express the existing static template as
DEFAULT_TEMPLATE using the same engine so there is a single rendering path. Add a templates table (id, client_id, name,
version, spec JSON) and endpoints: create, list, new-version update, validate, preview. Add optional template_id to POST /jobs
(default = built-in). Store template_id and template_version on each certificate.
Tests: valid render, each unsafe template rejected, long names, versioning keeps old certificates reproducible.
```

### Prompt C: Verification and search
```
Implement GET /verify/{code} (public, rate limited, exact code only) returning VALID / REVOKED / TAMPERED / NOT_FOUND /
INVALID_FORMAT. Reject bad checksums before querying the DB, recompute the HMAC signature on each call using
hmac.compare_digest, and mask the recipient email in the public response. Add GET /api/v1/certificates/search for
authenticated clients with filters q, code, name, email, course, job_id, status and pagination (page_size max 100),
always scoped by client_id. Add pg_trgm GIN indexes in an Alembic migration and escape LIKE wildcards in user input.
Write tests for every verification state, email masking, each search filter, and cross-tenant isolation.
Log every verification to the audit table.
```

---

## 7. How this fits your roadmap

| Where | What to build |
|---|---|
| **Phase 2** | Build the PDF generator **with the template engine from the start** (default template only). It costs little extra now and saves a rewrite later. |
| **Phase 7** | Add certificate codes, signatures, `/verify`, and revocation (Prompts A and C) |
| **After Phase 7** | Custom templates API (Prompt B endpoints), then the search endpoint |
| **Interview tip** | Be ready to explain *why JSON and not Jinja/HTML* (security) and *why public search is exact-code only* (privacy). These two answers show real engineering judgment. |
