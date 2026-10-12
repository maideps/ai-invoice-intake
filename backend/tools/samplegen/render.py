"""Draw a sample invoice as a one-page PDF in one of three layouts.

PDFs are written in ReportLab's invariant mode (fixed dates and document id) and without page
compression, so the same input gives the same bytes on every machine.
"""

from collections.abc import Callable
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, LETTER
from reportlab.pdfgen.canvas import Canvas

from .builder import Layout, Sample, format_date, format_money, format_number, format_quantity

MARGIN = 50.0
ROW = 18.0
GREY = colors.HexColor("#5F6B73")
BAND = colors.HexColor("#1F4E5F")
SHADE = colors.HexColor("#EEF3F5")


def render_pdf(sample: Sample) -> bytes:
    buffer = BytesIO()
    size = A4 if sample.vendor.page_size == "A4" else LETTER
    pdf = Canvas(buffer, pagesize=size, invariant=1, pageCompression=0)
    labels = sample.vendor.language.labels
    pdf.setTitle(f"{labels['title']} {sample.fields.invoice_number}")
    pdf.setAuthor(sample.vendor.name)
    pdf.setSubject("Synthetic sample invoice, not a real document")
    width, height = size
    _LAYOUTS[sample.layout](pdf, sample, width, height)
    _footer(pdf, sample, width)
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def _texts(sample: Sample) -> dict[str, str]:
    """Every value printed on the invoice, already formatted for the vendor's country."""
    vendor, fields = sample.vendor, sample.fields
    assert fields.issue_date and fields.due_date and fields.subtotal is not None
    assert fields.tax is not None and fields.total is not None
    return {
        "number": fields.invoice_number or "",
        "date": format_date(fields.issue_date, vendor.date_format),
        "due": format_date(fields.due_date, vendor.date_format),
        "subtotal": format_money(fields.subtotal, vendor),
        "tax": format_money(fields.tax, vendor),
        "total": format_money(fields.total, vendor),
        "terms": vendor.language.payment_terms.format(days=vendor.payment_days),
    }


def _classic(pdf: Canvas, sample: Sample, width: float, height: float) -> None:
    vendor, labels, text = sample.vendor, sample.vendor.language.labels, _texts(sample)
    right = width - MARGIN
    y = height - 60

    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(MARGIN, y, vendor.name)
    pdf.setFont("Helvetica", 9)
    for i, line in enumerate(vendor.address, start=1):
        pdf.drawString(MARGIN, y - 4 - 12 * i, line)

    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawRightString(right, y, labels["title"])
    for i, key in enumerate(("number", "date", "due"), start=1):
        row_y = y - 8 - 15 * i
        pdf.setFont("Helvetica", 9.5)
        pdf.drawString(right - 200, row_y, labels[key])
        pdf.setFont("Helvetica-Bold", 9.5)
        pdf.drawRightString(right, row_y, text[key])

    y = height - 175
    pdf.setFont("Helvetica-Bold", 10)
    pdf.drawString(MARGIN, y, labels["bill_to"])
    pdf.setFont("Helvetica", 10)
    for i, line in enumerate((sample.customer.name, *sample.customer.address), start=1):
        pdf.drawString(MARGIN, y - 13 * i, line)

    y = height - 265
    pdf.setFont("Helvetica-Bold", 9.5)
    _table_header(pdf, labels, y, right)
    pdf.setLineWidth(0.8)
    pdf.line(MARGIN, y - 6, right, y - 6)
    pdf.setFont("Helvetica", 9.5)
    y = _table_rows(pdf, sample, y - ROW - 4, right, shade=False)
    pdf.line(MARGIN, y + ROW - 6, right, y + ROW - 6)

    _totals(pdf, sample, text, y - 10, right, label_x=right - 200)
    pdf.setFont("Helvetica", 9)
    pdf.setFillColor(GREY)
    pdf.drawString(MARGIN, y - 95, text["terms"])
    pdf.setFillColor(colors.black)


def _banner(pdf: Canvas, sample: Sample, width: float, height: float) -> None:
    vendor, labels, text = sample.vendor, sample.vendor.language.labels, _texts(sample)
    left, right = 40.0, width - 40

    pdf.setFillColor(BAND)
    pdf.rect(0, height - 80, width, 80, fill=1, stroke=0)
    pdf.setFillColor(colors.white)
    pdf.setFont("Helvetica-Bold", 18)
    pdf.drawString(left, height - 48, vendor.name)
    pdf.setFont("Helvetica", 14)
    pdf.drawRightString(right, height - 48, labels["title"])

    pdf.setFillColor(GREY)
    pdf.setFont("Helvetica", 8.5)
    pdf.drawString(left, height - 98, "  |  ".join(vendor.address))

    box_y, box_w = height - 160, (right - left - 20) / 3
    for i, key in enumerate(("number", "date", "due")):
        x = left + i * (box_w + 10)
        pdf.setStrokeColor(colors.lightgrey)
        pdf.rect(x, box_y, box_w, 40, fill=0, stroke=1)
        pdf.setFillColor(GREY)
        pdf.setFont("Helvetica", 8)
        pdf.drawString(x + 8, box_y + 26, labels[key].upper())
        pdf.setFillColor(colors.black)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawString(x + 8, box_y + 10, text[key])

    y = height - 195
    pdf.setFont("Helvetica-Bold", 9)
    pdf.setFillColor(GREY)
    pdf.drawString(left, y, labels["bill_to"].upper())
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica", 10)
    pdf.drawString(left, y - 14, ", ".join((sample.customer.name, *sample.customer.address)))

    y = height - 250
    pdf.setFillColor(SHADE)
    pdf.rect(left, y - 6, right - left, ROW, fill=1, stroke=0)
    pdf.setFillColor(colors.black)
    pdf.setFont("Helvetica-Bold", 9.5)
    _table_header(pdf, labels, y, right - 8, left=left + 8)
    pdf.setFont("Helvetica", 9.5)
    y = _table_rows(pdf, sample, y - ROW, right - 8, left=left + 8, shade=True)

    box_top = y - 4
    pdf.setStrokeColor(BAND)
    pdf.rect(right - 230, box_top - 62, 230, 62, fill=0, stroke=1)
    _totals(pdf, sample, text, box_top - 6, right - 10, label_x=right - 220)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(left, box_top - 90, text["terms"])


def _compact(pdf: Canvas, sample: Sample, width: float, height: float) -> None:
    vendor, fields = sample.vendor, sample.fields
    labels, text = vendor.language.labels, _texts(sample)
    rule = "-" * 72
    lines = [
        vendor.name,
        *vendor.address,
        rule,
        f"{labels['title']}  {text['number']}",
        f"{labels['date']}: {text['date']}",
        f"{labels['due']}: {text['due']}",
        f"{labels['bill_to']}: {sample.customer.name}",
        f"    {', '.join(sample.customer.address)}",
        rule,
    ]
    for item in fields.line_items:
        lines.append(f"{format_quantity(item.quantity, vendor)} x {item.description}")
        price = format_money(item.unit_price, vendor)
        lines.append(f"      @ {price} = {format_money(item.amount, vendor)}")
    lines += [
        rule,
        f"{labels['subtotal']}: {text['subtotal']}",
        f"{vendor.tax_label}: {text['tax']}",
        f"{labels['total']}: {text['total']}",
        "",
        text["terms"],
    ]
    pdf.setFont("Courier", 9.5)
    for i, line in enumerate(lines):
        pdf.drawString(MARGIN, height - 60 - 13 * i, line)


def _table_header(
    pdf: Canvas, labels: dict[str, str], y: float, right: float, left: float = MARGIN
) -> None:
    pdf.drawString(left, y, labels["description"])
    pdf.drawRightString(right - 190, y, labels["quantity"])
    pdf.drawRightString(right - 95, y, labels["unit_price"])
    pdf.drawRightString(right, y, labels["amount"])


def _table_rows(
    pdf: Canvas, sample: Sample, y: float, right: float, *, shade: bool, left: float = MARGIN
) -> float:
    """Draw the line items from ``y`` down; return the y below the last row."""
    vendor = sample.vendor
    for i, line in enumerate(sample.fields.line_items):
        if shade and i % 2 == 1:
            pdf.setFillColor(SHADE)
            pdf.rect(left - 8, y - 6, right - left + 16, ROW, fill=1, stroke=0)
            pdf.setFillColor(colors.black)
        pdf.drawString(left, y, line.description)
        pdf.drawRightString(right - 190, y, format_quantity(line.quantity, vendor))
        pdf.drawRightString(right - 95, y, format_number(line.unit_price, vendor))
        pdf.drawRightString(right, y, format_number(line.amount, vendor))
        y -= ROW
    return y


def _totals(
    pdf: Canvas, sample: Sample, text: dict[str, str], y: float, right: float, label_x: float
) -> None:
    labels = sample.vendor.language.labels
    rows = (
        (labels["subtotal"], text["subtotal"], False),
        (sample.vendor.tax_label, text["tax"], False),
        (labels["total"], text["total"], True),
    )
    for i, (label, value, bold) in enumerate(rows):
        pdf.setFont("Helvetica-Bold" if bold else "Helvetica", 11 if bold else 9.5)
        pdf.drawString(label_x, y - 16 * i - 10, label)
        pdf.drawRightString(right, y - 16 * i - 10, value)


def _footer(pdf: Canvas, sample: Sample, width: float) -> None:
    pdf.setFont("Helvetica-Oblique", 7.5)
    pdf.setFillColor(GREY)
    pdf.drawCentredString(
        width / 2, 28, f"SYNTHETIC SAMPLE - generated test data, not a real invoice - {sample.name}"
    )


_LAYOUTS: dict[Layout, Callable[[Canvas, Sample, float, float], None]] = {
    "classic": _classic,
    "banner": _banner,
    "compact": _compact,
}
