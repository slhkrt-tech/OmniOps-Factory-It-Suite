"""QR/barkod etiket PDF üretimi (ReportLab)."""
import io

from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def _draw_qr(c, x, y, size_mm, value):
    """Belirtilen konuma QR kod çizer."""
    qr = QrCodeWidget(value=value)
    bounds = qr.getBounds()
    width = bounds[2] - bounds[0] or 1
    height = bounds[3] - bounds[1] or 1
    drawing = Drawing(
        size_mm * mm,
        size_mm * mm,
        transform=[size_mm * mm / width, 0, 0, size_mm * mm / height, 0, 0],
    )
    drawing.add(qr)
    drawing.drawOn(c, x, y)


def build_qr_labels_pdf(tags, base_url=''):
    """Tek veya çoklu QR etiketini A4 PDF olarak üretir."""
    buffer = io.BytesIO()
    page_width, page_height = A4
    label_width = 95 * mm
    label_height = 50 * mm
    margin_x = 10 * mm
    margin_y = 12 * mm
    cols = 2
    rows = 5

    c = canvas.Canvas(buffer, pagesize=A4)
    c.setTitle('OmniOps QR Etiketleri')

    for index, tag in enumerate(tags):
        slot = index % (cols * rows)
        if index and slot == 0:
            c.showPage()

        col = slot % cols
        row = slot // cols
        x = margin_x + col * label_width
        y = page_height - margin_y - (row + 1) * label_height

        qr_value = tag.code
        if base_url:
            qr_value = f'{base_url.rstrip("/")}/api/qr-lookup/?code={tag.code}'

        _draw_qr(c, x + 4 * mm, y + 12 * mm, 32, qr_value)

        c.setFont('Helvetica-Bold', 10)
        c.drawString(x + 40 * mm, y + label_height - 14 * mm, tag.display_name[:28])
        c.setFont('Helvetica', 9)
        c.drawString(x + 40 * mm, y + label_height - 26 * mm, tag.code[:24])
        c.drawString(x + 40 * mm, y + label_height - 38 * mm, tag.get_tag_type_display()[:22])
        if tag.location:
            c.setFont('Helvetica', 8)
            c.drawString(x + 4 * mm, y + 4 * mm, tag.location[:40])

        c.setStrokeColorRGB(0.82, 0.86, 0.9)
        c.rect(x, y, label_width - 4 * mm, label_height - 2 * mm, stroke=1, fill=0)

    c.save()
    buffer.seek(0)
    return buffer
