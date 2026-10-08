from app.templates_engine.schema import Page, TextEl, RectEl, LineEl, QrEl

DEFAULT_TEMPLATE = Page(
    width_mm=297, # A4 Landscape
    height_mm=210,
    elements=[
        # Double Border (Navy + Gold)
        RectEl(x=10, y=10, width=277, height=190, stroke="#000080", stroke_width=2), # Navy
        RectEl(x=12, y=12, width=273, height=186, stroke="#D4AF37", stroke_width=1), # Gold

        # Title
        TextEl(
            x=148.5, y=40, content="CERTIFICATE OF ACHIEVEMENT",
            font="Helvetica-Bold", size=32, align="center", max_width_mm=200
        ),

        # Recipient Name
        TextEl(
            x=148.5, y=80, content="{{recipient_name}}",
            font="Times-Bold", size=24, align="center", max_width_mm=200
        ),

        # Course
        TextEl(
            x=148.5, y=100, content="for successful completion of",
            font="Helvetica", size=14, align="center", max_width_mm=200
        ),
        TextEl(
            x=148.5, y=110, content="{{course_name}}",
            font="Helvetica-Bold", size=18, align="center", max_width_mm=200
        ),

        # Achievement Line
        TextEl(
            x=148.5, y=130, content="{{achievement_text}}",
            font="Helvetica", size=12, align="center", max_width_mm=200
        ),

        # Issue Date (Bottom Left)
        TextEl(
            x=40, y=170, content="Issued on: {{issue_date}}",
            font="Helvetica", size=10, align="left", max_width_mm=100
        ),

        # QR Code (Bottom Left, next to date)
        QrEl(x=20, y=150, size=30),

        # Signature Line (Bottom Right)
        LineEl(x=200, y=165, x2=260, y2=165, stroke="#000000", stroke_width=1),
        TextEl(
            x=230, y=170, content="{{issuer_name}}",
            font="Helvetica", size=12, align="center", max_width_mm=60
        ),

        # Certificate ID (Bottom Center)
        TextEl(
            x=148.5, y=190, content="ID: {{certificate_code}}",
            font="Courier", size=8, align="center", max_width_mm=100
        ),
    ]
)
