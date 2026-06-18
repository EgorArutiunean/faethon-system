from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.documents import Document, DocumentLine
from app.models.products import Product


TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "templates" / "invoice.html"
FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed.ttf"),
    Path("C:/Windows/Fonts/arial.ttf"),
]

ONES = {
    0: "",
    1: "один",
    2: "два",
    3: "три",
    4: "четыре",
    5: "пять",
    6: "шесть",
    7: "семь",
    8: "восемь",
    9: "девять",
    10: "десять",
    11: "одиннадцать",
    12: "двенадцать",
    13: "тринадцать",
    14: "четырнадцать",
    15: "пятнадцать",
    16: "шестнадцать",
    17: "семнадцать",
    18: "восемнадцать",
    19: "девятнадцать",
}
FEMININE_ONES = {1: "одна", 2: "две"}
TENS = {2: "двадцать", 3: "тридцать", 4: "сорок", 5: "пятьдесят", 6: "шестьдесят", 7: "семьдесят", 8: "восемьдесят", 9: "девяносто"}
HUNDREDS = {1: "сто", 2: "двести", 3: "триста", 4: "четыреста", 5: "пятьсот", 6: "шестьсот", 7: "семьсот", 8: "восемьсот", 9: "девятьсот"}


def _text(value: object) -> str:
    return escape("" if value is None else str(value))


def _money(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.2f}"


def _price(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.3f}"


def _quantity(value: Decimal | None) -> str:
    return "" if value is None else f"{value:.3f}".rstrip("0").rstrip(".")


def _document_date(document: Document) -> str:
    return document.document_date.strftime("%Y.%m.%d")


def _triad_words(value: int, feminine: bool = False) -> list[str]:
    words: list[str] = []
    hundreds = value // 100
    rest = value % 100
    if hundreds:
        words.append(HUNDREDS[hundreds])
    if 10 <= rest <= 19:
        words.append(ONES[rest])
        return words
    tens = rest // 10
    ones = rest % 10
    if tens:
        words.append(TENS[tens])
    if ones:
        words.append((FEMININE_ONES if feminine else ONES).get(ones, ONES[ones]))
    return words


def _plural(value: int, one: str, few: str, many: str) -> str:
    tail = value % 100
    if 11 <= tail <= 14:
        return many
    last = value % 10
    if last == 1:
        return one
    if 2 <= last <= 4:
        return few
    return many


def _integer_words(value: int) -> str:
    if value == 0:
        return "ноль"
    parts: list[str] = []
    thousands = value // 1000
    remainder = value % 1000
    if thousands:
        parts.extend(_triad_words(thousands, feminine=True))
        parts.append(_plural(thousands, "тысяча", "тысячи", "тысяч"))
    if remainder:
        parts.extend(_triad_words(remainder))
    return " ".join(parts)


def _amount_words(value: Decimal | None) -> str:
    amount = value or Decimal("0")
    rubles = int(amount)
    kopecks = int((amount - Decimal(rubles)) * 100)
    words = _integer_words(rubles).capitalize()
    return f"( {words} {_plural(rubles, 'рубль', 'рубля', 'рублей')} {kopecks:02d} копеек )"


def _line_rows(document: Document) -> str:
    rows: list[str] = []
    for index, line in enumerate(document.lines, start=1):
        product = line.product
        rows.append(
            "<tr>"
            f"<td class=\"center\">{index}</td>"
            f"<td class=\"center\">{_text(product.sku if product else line.product_id)}</td>"
            f"<td>{_text(line.product_name or line.product_id)}</td>"
            f"<td class=\"center\">{_text(product.unit.short_name if product and product.unit else 'шт')}</td>"
            f"<td class=\"num\">{_quantity(line.quantity)}</td>"
            f"<td class=\"num\">{_price(line.price)}</td>"
            f"<td class=\"num strong\">{_money(line.line_total)}</td>"
            "</tr>"
        )
    if not rows:
        rows.append("<tr><td colspan=\"7\" class=\"empty\">\u041d\u0435\u0442 \u0441\u0442\u0440\u043e\u043a</td></tr>")
    return "\n".join(rows)


def _document_title(document: Document) -> str:
    if document.document_type == Document.TYPE_INCOMING:
        return "\u041f\u0420\u0418\u0425\u041e\u0414\u041d\u0410\u042f \u041d\u0410\u041a\u041b\u0410\u0414\u041d\u0410\u042f"
    if document.document_type == Document.TYPE_OUTGOING:
        return "\u0420\u0410\u0421\u0425\u041e\u0414\u041d\u0410\u042f \u041d\u0410\u041a\u041b\u0410\u0414\u041d\u0410\u042f"
    if document.document_type == Document.TYPE_TRANSFER:
        return "\u041d\u0410\u041a\u041b\u0410\u0414\u041d\u0410\u042f \u041d\u0410 \u041f\u0415\u0420\u0415\u041c\u0415\u0429\u0415\u041d\u0418\u0415"
    if document.document_type == Document.TYPE_ADJUSTMENT:
        return "\u0410\u041a\u0422 \u041a\u041e\u0420\u0420\u0415\u041a\u0426\u0418\u0418 \u041e\u0421\u0422\u0410\u0422\u041a\u041e\u0412"
    return "\u0414\u041e\u041a\u0423\u041c\u0415\u041d\u0422"


def _document_number(document: Document) -> str:
    return document.number or str(document.id)


def _watermark(document: Document) -> str:
    if document.status == Document.STATUS_DRAFT:
        return "<div class=\"watermark\">\u0427\u0415\u0420\u041d\u041e\u0412\u0418\u041a</div>"
    if document.status == Document.STATUS_CANCELLED:
        return "<div class=\"watermark danger\">\u041e\u0422\u041c\u0415\u041d\u0401\u041d</div>"
    return ""


def _load_print_document(db: Session, document_id: int) -> Document:
    document = db.scalar(
        select(Document)
        .where(Document.id == document_id)
        .options(
            selectinload(Document.partner),
            selectinload(Document.warehouse),
            selectinload(Document.destination_warehouse),
            selectinload(Document.lines).selectinload(DocumentLine.product).selectinload(Product.unit),
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


def get_invoice_html(db: Session, document_id: int) -> str:
    document = _load_print_document(db, document_id)

    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    values = {
        "document_title": _text(_document_title(document)),
        "document_number": _text(_document_number(document)),
        "document_date": _text(_document_date(document)),
        "supplier_name": _text(document.warehouse_name or ""),
        "buyer_name": _text(document.partner_name or ""),
        "note": _text(document.note or ""),
        "total_amount": _money(document.total_amount),
        "amount_words": _text(_amount_words(document.total_amount)),
        "line_rows": _line_rows(document),
        "watermark": _watermark(document),
    }
    for key, value in values.items():
        template = template.replace(f"{{{{{key}}}}}", value)
    return template


def _pdf_font_path() -> Path:
    for path in FONT_CANDIDATES:
        if path.exists():
            return path
    raise HTTPException(status_code=500, detail="PDF font not found")


def get_invoice_pdf(db: Session, document_id: int) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    document = _load_print_document(db, document_id)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    font_name = "BuyDejaVu"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont(font_name, str(_pdf_font_path())))

    def draw_text(x: float, y: float, text: object, size: int = 10, align: str = "left", max_width: float | None = None) -> None:
        value = "" if text is None else str(text)
        pdf.setFont(font_name, size)
        if max_width is not None:
            while value and pdfmetrics.stringWidth(value, font_name, size) > max_width:
                value = value[:-1]
            if value != ("" if text is None else str(text)):
                value = value[:-1] + "."
        text_width = pdfmetrics.stringWidth(value, font_name, size)
        if align == "center":
            x -= text_width / 2
        elif align == "right":
            x -= text_width
        pdf.drawString(x, y, value)

    pdf.setLineWidth(0.7)
    title = f"{_document_title(document)} № {_document_number(document)}"
    draw_text(width / 2, height - 52, title, 14, align="center")

    y = height - 84
    draw_text(44, y, "Дата:", 10)
    draw_text(110, y, _document_date(document), 10)
    y -= 18
    draw_text(44, y, "Поставщик:", 10)
    draw_text(110, y, document.warehouse_name or "", 10, max_width=420)
    y -= 18
    draw_text(44, y, "Покупатель:", 10)
    draw_text(122, y, document.partner_name or "", 10, max_width=223)
    draw_text(362, y, "Доверенность №:", 10)
    draw_text(480, y, "от:", 10)
    y -= 18
    draw_text(44, y, "Отпущено:", 10)
    draw_text(110, y, document.note or "", 10, max_width=420)

    table_x = 34
    table_y = height - 174
    row_h = 20
    col_widths = [28, 58, 250, 36, 48, 64, 70]
    headers = ["№", "Код", "Товар", "Ед.", "Кол.", "Цена", "Сумма"]
    x = table_x
    for width, header in zip(col_widths, headers):
        pdf.rect(x, table_y, width, row_h)
        draw_text(x + width / 2, table_y + 7, header, 8, align="center")
        x += width

    current_y = table_y - row_h
    for index, line in enumerate(document.lines, start=1):
        product = line.product
        row_values = [
            str(index),
            product.sku if product else line.product_id,
            line.product_name or line.product_id,
            product.unit.short_name if product and product.unit else "шт",
            _quantity(line.quantity),
            _price(line.price),
            _money(line.line_total),
        ]
        x = table_x
        max_widths = [20, 50, 238, 28, 40, 56, 62]
        aligns = ["center", "center", "left", "center", "right", "right", "right"]
        for width, value, max_width, align in zip(col_widths, row_values, max_widths, aligns):
            pdf.rect(x, current_y, width, row_h)
            text_x = x + 4 if align == "left" else x + width / 2 if align == "center" else x + width - 4
            draw_text(text_x, current_y + 7, value, 8, align=align, max_width=max_width)
            x += width
        current_y -= row_h

    if not document.lines:
        pdf.rect(table_x, current_y, sum(col_widths), row_h)
        draw_text(width / 2, current_y + 7, "Нет строк", 8, align="center")
        current_y -= row_h

    total_y = current_y - 16
    draw_text(120, total_y, "Итого:", 10, align="right")
    draw_text(555, total_y, _money(document.total_amount), 10, align="right")
    draw_text(88, total_y - 22, _amount_words(document.total_amount), 10, max_width=430)
    draw_text(72, total_y - 112, "Отпустил", 10)
    pdf.line(140, total_y - 110, 260, total_y - 110)
    draw_text(340, total_y - 112, "Получил", 10)
    pdf.line(405, total_y - 110, 525, total_y - 110)

    pdf.showPage()
    pdf.save()
    return buffer.getvalue()
