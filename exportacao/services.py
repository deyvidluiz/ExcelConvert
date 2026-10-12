from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from docx import Document as WordDocument
from docx.enum.section import WD_ORIENT
from docx.shared import Inches


def extraction_for(document):
    from documentos.models import ExtractionCache

    cache = ExtractionCache.objects.filter(sha256=document.sha256).order_by("-created_at").first()
    if not cache:
        raise ValueError("Os dados ainda não foram processados.")
    return cache.payload


def _value(cell):
    if isinstance(cell, dict):
        return cell.get("value")
    return cell


def _tables(payload):
    for page in payload.get("pages", []):
        for table in page.get("tables", []):
            yield page, table


def build_xlsx(payload):
    workbook = Workbook()
    workbook.remove(workbook.active)
    thin = Side(style="thin", color="D7DEE8")
    for index, (page, table) in enumerate(_tables(payload), start=1):
        sheet = workbook.create_sheet(title=f"P{page.get('page_number', index)} T{index}"[:31])
        title = table.get("title") or f"Página {page.get('page_number', index)}"
        sheet.cell(1, 1, title).font = Font(bold=True, size=13, color="182230")
        headers = table.get("headers", [])
        rows = table.get("rows", [])
        for col, cell in enumerate(headers, start=1):
            target = sheet.cell(3, col, _value(cell))
            target.font = Font(bold=True, color="FFFFFF")
            target.fill = PatternFill("solid", fgColor="3C5CCF")
            target.alignment = Alignment(horizontal="center", vertical="center")
        for row_index, row in enumerate(rows, start=4):
            for col, cell in enumerate(row, start=1):
                target = sheet.cell(row_index, col, _value(cell))
                target.number_format = "@"
                target.quotePrefix = True
                target.alignment = Alignment(vertical="top", wrap_text=True)
        for row in sheet.iter_rows(min_row=3, max_row=max(3, sheet.max_row), min_col=1, max_col=max(1, sheet.max_column)):
            for cell in row:
                cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
        for col in range(1, max(1, sheet.max_column) + 1):
            sheet.column_dimensions[get_column_letter(col)].width = 20
        for merged in table.get("merged_cells", []):
            try:
                sheet.merge_cells(merged)
            except ValueError:
                pass
        sheet.freeze_panes = "A4"
    if not workbook.worksheets:
        workbook.create_sheet("Sem tabelas")
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output


def build_docx(payload):
    document = WordDocument()
    section = document.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    for index, (page, table_data) in enumerate(_tables(payload), start=1):
        if index > 1:
            document.add_page_break()
        document.add_heading(table_data.get("title") or f"Página {page.get('page_number', index)}", level=2)
        headers = [_value(cell) or "" for cell in table_data.get("headers", [])]
        rows = [[_value(cell) or "" for cell in row] for row in table_data.get("rows", [])]
        table = document.add_table(rows=1, cols=max(1, len(headers)))
        table.style = "Table Grid"
        for cell, value in zip(table.rows[0].cells, headers):
            cell.text = str(value)
        for row in rows:
            cells = table.add_row().cells
            for cell, value in zip(cells, row):
                cell.text = str(value)
    output = BytesIO()
    document.save(output)
    output.seek(0)
    return output


def build_pdf(payload):
    output = BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), leftMargin=12 * mm, rightMargin=12 * mm, topMargin=12 * mm, bottomMargin=12 * mm)
    styles = getSampleStyleSheet()
    story = []
    for index, (page, table_data) in enumerate(_tables(payload), start=1):
        if index > 1:
            story.append(PageBreak())
        story.extend([Paragraph(str(table_data.get("title") or f"Página {page.get('page_number', index)}"), styles["Heading2"]), Spacer(1, 5 * mm)])
        data = [[str(_value(cell) or "") for cell in table_data.get("headers", [])]]
        data.extend([[str(_value(cell) or "") for cell in row] for row in table_data.get("rows", [])])
        if not data[0]:
            data = [["Sem dados"]]
        table = Table(data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3C5CCF")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D7DEE8")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
        ]))
        story.append(table)
    if not story:
        story.append(Paragraph("Nenhuma tabela encontrada.", styles["BodyText"]))
    doc.build(story)
    output.seek(0)
    return output
