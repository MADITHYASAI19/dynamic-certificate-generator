from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import Optional, Union, List, Literal
from typing import Annotated

# Constants for allow-lists
ALLOWED_FONTS = {"Helvetica", "Helvetica-Bold", "Times-Roman", "Times-Bold", "Courier"}
ALLOWED_PLACEHOLDERS = {
    "recipient_name", "course_name", "issue_date", "issuer_name",
    "certificate_code", "achievement_text", "grade", "verify_url"
}

class BaseElement(BaseModel):
    model_config = ConfigDict(extra="forbid")
    x: float = Field(..., ge=0, le=600)
    y: float = Field(..., ge=0, le=600)

class TextEl(BaseElement):
    type: Literal["text"] = "text"
    content: str
    font: str = "Helvetica"
    size: float = Field(12, ge=6, le=120)
    min_size: float = Field(6, ge=6, le=120)
    max_width_mm: float = Field(100, ge=0, le=600)
    color: str = "#000000"
    align: Literal["left", "center", "right"] = "left"

    @field_validator("font")
    @classmethod
    def validate_font(cls, v):
        if v not in ALLOWED_FONTS:
            raise ValueError(f"Font {v} is not allowed. Use one of {ALLOWED_FONTS}")
        return v

class RectEl(BaseElement):
    type: Literal["rect"] = "rect"
    width: float = Field(..., ge=0, le=600)
    height: float = Field(..., ge=0, le=600)
    fill: Optional[str] = None
    stroke: Optional[str] = None
    stroke_width: float = Field(0, ge=0, le=20)

class LineEl(BaseElement):
    type: Literal["line"] = "line"
    x2: float = Field(..., ge=0, le=600)
    y2: float = Field(..., ge=0, le=600)
    stroke: str = "#000000"
    stroke_width: float = Field(1, ge=0, le=20)

class QrEl(BaseElement):
    type: Literal["qr"] = "qr"
    size: float = Field(20, ge=10, le=200)

class Page(BaseModel):
    width_mm: float = Field(297, ge=50, le=600)
    height_mm: float = Field(210, ge=50, le=600)
    elements: List[Union[TextEl, RectEl, LineEl, QrEl]] = Field(..., max_length=60)

    @model_validator(mode="after")
    def validate_must_have_code_or_qr(self) -> "Page":
        has_qr = any(isinstance(e, QrEl) for e in self.elements)
        has_code = any(
            isinstance(e, TextEl) and "{{certificate_code}}" in e.content
            for e in self.elements
        )
        if not (has_qr or has_code):
            raise ValueError("Template must contain at least one QR element or {{certificate_code}} placeholder")
        return self
