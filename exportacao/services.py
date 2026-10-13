import posixpath
import re
import zipfile
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree
from django.conf import settings

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import MergedCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils.cell import range_boundaries
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
    if document.extraction_payload:
        return document.extraction_payload
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


def build_xlsx_from_template(payload, excel_template):
    """Preenche um modelo cadastrado preservando estrutura, estilos e fórmulas."""
    raw_template = excel_template.workbook.read()
    keep_vba = Path(excel_template.workbook.name or "").suffix.lower() == ".xlsm"
    workbook = _load_template_workbook(raw_template, keep_vba=keep_vba)
    mappings = {mapping.field.field_id: mapping for mapping in excel_template.mappings.select_related("field")}
    written_cells = set()
    for field in payload.get("template_fields", []):
        mapping = mappings.get(field.get("field_id"))
        if not mapping or mapping.sheet_name not in workbook.sheetnames:
            continue
        cells = _mapping_cells(workbook[mapping.sheet_name], mapping.cell_or_range)
        values = _values_for_cells(field.get("value"), len(cells), field.get("field_id"))
        for cell, value in zip(cells, values):
            if cell.data_type == "f":
                raise ValueError("O mapeamento {} aponta para uma fórmula em {}.".format(field.get("field_id"), cell.coordinate))
            cell.value = value
            written_cells.add((mapping.sheet_name, cell.coordinate))
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    preserved_output = _preserve_template_parts(_decrypt_template_bytes(raw_template), output.getvalue())
    _validate_saved_template(raw_template, preserved_output, keep_vba=keep_vba, written_cells=written_cells)
    return BytesIO(preserved_output)


def _decrypt_template_bytes(raw_template):
    if raw_template.startswith(b"PK" + bytes((3, 4))):
        return raw_template
    if not raw_template.startswith(bytes.fromhex("d0cf11e0a1b11ae1")):
        raise ValueError("O arquivo do modelo não é um XLSX/XLSM reconhecido.")
    password = getattr(settings, "EXCEL_TEMPLATE_PASSWORD", "")
    if not password:
        raise ValueError("EXCEL_TEMPLATE_PASSWORD não está configurada para o modelo Excel protegido.")
    try:
        import msoffcrypto
    except ImportError as exc:
        raise ValueError("A dependência msoffcrypto-tool é necessária para abrir o modelo Excel protegido.") from exc
    decrypted = BytesIO()
    try:
        office = msoffcrypto.OfficeFile(BytesIO(raw_template))
        office.load_key(password=password)
        office.decrypt(decrypted)
    except Exception as exc:
        raise ValueError("Não foi possível abrir o modelo Excel protegido com a senha configurada.") from exc
    return decrypted.getvalue()


def _load_template_workbook(raw_template, *, keep_vba=False):
    """Abre XLSX normal ou pacote Office cifrado sem expor a senha."""
    return load_workbook(BytesIO(_decrypt_template_bytes(raw_template)), keep_vba=keep_vba, data_only=False)


def _mapping_cells(sheet, cell_or_range):
    """Expande células e intervalos, aceitando grupos separados por ';'."""
    addresses = [part.strip() for part in re.split(r"[;,]", cell_or_range or "") if part.strip()]
    cells = []
    for address in addresses:
        try:
            min_col, min_row, max_col, max_row = range_boundaries(address)
        except ValueError as exc:
            raise ValueError("Destino Excel inválido: {}".format(address)) from exc
        for row in sheet.iter_rows(min_row=min_row, max_row=max_row, min_col=min_col, max_col=max_col):
            for cell in row:
                if isinstance(cell, MergedCell):
                    raise ValueError(
                        "Destino Excel não pode ser uma célula mesclada secundária: {}!{}".format(
                            sheet.title, cell.coordinate
                        )
                    )
                cells.append(cell)
    if not cells:
        raise ValueError("Destino Excel vazio: {}".format(cell_or_range))
    return cells


def _values_for_cells(value, cell_count, field_id):
    if isinstance(value, dict):
        value = value.get("values", value.get("value"))
    if isinstance(value, (list, tuple)):
        if len(value) != cell_count:
            raise ValueError("O campo {} exige {} valores; foram recebidos {}.".format(field_id, cell_count, len(value)))
        return list(value)
    if cell_count != 1:
        raise ValueError(
            "O campo {} está mapeado para {} células e precisa de uma lista estruturada.".format(field_id, cell_count)
        )
    return [value]


def _preserve_template_parts(raw_template, output):
    """Restaura partes OOXML que o openpyxl não modela, como impressão e metadados."""
    source_zip = zipfile.ZipFile(BytesIO(raw_template))
    output_zip = zipfile.ZipFile(BytesIO(output))
    source_names = set(source_zip.namelist())
    output_parts = {name: output_zip.read(name) for name in output_zip.namelist()}
    rel_ns = "http://schemas.openxmlformats.org/package/2006/relationships"
    main_ns = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
    rel_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    ElementTree.register_namespace("", main_ns)
    ElementTree.register_namespace("r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships")

    content_types_name = "[Content_Types].xml"
    content_types = ElementTree.fromstring(output_parts[content_types_name])
    existing_overrides = {item.attrib.get("PartName") for item in content_types}
    for name in sorted(source_names - set(output_parts)):
        if name.startswith(("xl/printerSettings/", "xl/customProperty", "docMetadata/")):
            output_parts[name] = source_zip.read(name)
            source_content = ElementTree.fromstring(source_zip.read(content_types_name))
            for item in source_content:
                part_name = item.attrib.get("PartName", "")
                if part_name.lstrip("/") == name and part_name not in existing_overrides:
                    content_types.append(item)
                    existing_overrides.add(part_name)

    for rels_name in sorted(name for name in source_names if name.startswith("xl/worksheets/_rels/") and name.endswith(".rels")):
        source_rels = ElementTree.fromstring(source_zip.read(rels_name))
        output_rels_name = rels_name
        if output_rels_name not in output_parts:
            continue
        output_rels = ElementTree.fromstring(output_parts[output_rels_name])
        used_ids = {item.attrib.get("Id") for item in output_rels}
        next_id = 1
        replacements = {}
        source_dir = posixpath.dirname(posixpath.dirname(rels_name))
        for relationship in source_rels:
            rel_type = relationship.attrib.get("Type", "")
            if not rel_type.endswith(("/printerSettings", "/customProperty")):
                continue
            target = relationship.attrib.get("Target", "")
            source_part = posixpath.normpath(posixpath.join(source_dir, target))
            if source_part not in output_parts and source_part in source_names:
                output_parts[source_part] = source_zip.read(source_part)
            if source_part not in output_parts:
                continue
            while "rId{}".format(next_id) in used_ids:
                next_id += 1
            new_id = "rId{}".format(next_id)
            next_id += 1
            copied = dict(relationship.attrib)
            copied["Id"] = new_id
            output_rels.append(ElementTree.Element(relationship.tag, copied))
            used_ids.add(new_id)
            replacements[relationship.attrib.get("Id")] = new_id

        sheet_name = rels_name.replace("/_rels/", "/").removesuffix(".rels")
        if sheet_name in output_parts and replacements:
            source_sheet_xml = ElementTree.fromstring(source_zip.read(sheet_name))
            source_page_setup_ids = [
                page_setup.attrib.get(rel_attr)
                for page_setup in source_sheet_xml.iter("{" + main_ns + "}pageSetup")
                if page_setup.attrib.get(rel_attr)
            ]
            sheet_xml = ElementTree.fromstring(output_parts[sheet_name])
            for page_setup in sheet_xml.iter("{" + main_ns + "}pageSetup"):
                current_id = page_setup.attrib.get(rel_attr)
                original_id = current_id or (source_page_setup_ids[0] if source_page_setup_ids else None)
                if original_id in replacements:
                    page_setup.attrib[rel_attr] = replacements[original_id]
            output_parts[sheet_name] = ElementTree.tostring(sheet_xml, encoding="utf-8", xml_declaration=True)
        output_parts[output_rels_name] = ElementTree.tostring(output_rels, encoding="utf-8", xml_declaration=True)

    output_parts[content_types_name] = ElementTree.tostring(content_types, encoding="utf-8", xml_declaration=True)
    restored = BytesIO()
    with zipfile.ZipFile(restored, "w", zipfile.ZIP_DEFLATED) as destination:
        for name, data in output_parts.items():
            destination.writestr(name, data)
    return restored.getvalue()


def _workbook_signature(workbook):
    formulas = {}
    sheets = {}
    for sheet in workbook.worksheets:
        sheets[sheet.title] = {
            "dimension": sheet.calculate_dimension(),
            "merged": sorted(str(item) for item in sheet.merged_cells.ranges),
            "print_area": str(sheet.print_area),
            "orientation": sheet.page_setup.orientation,
            "paper_size": sheet.page_setup.paperSize,
            "column_widths": sorted((key, value.width, value.hidden) for key, value in sheet.column_dimensions.items()),
            "row_heights": sorted((key, value.height, value.hidden) for key, value in sheet.row_dimensions.items()),
            "images": len(sheet._images),
            "charts": len(sheet._charts),
        }
        for row in sheet.iter_rows():
            for cell in row:
                if cell.data_type == "f":
                    formulas[(sheet.title, cell.coordinate)] = cell.value
    return {"sheetnames": list(workbook.sheetnames), "sheets": sheets, "formulas": formulas}


def _validate_saved_template(raw_template, output, *, keep_vba, written_cells):
    before = _workbook_signature(_load_template_workbook(raw_template, keep_vba=keep_vba))
    after_workbook = load_workbook(BytesIO(output), keep_vba=keep_vba, data_only=False)
    after = _workbook_signature(after_workbook)
    if before["sheetnames"] != after["sheetnames"] or before["sheets"] != after["sheets"]:
        raise ValueError("A exportação alterou a estrutura, mesclagens, impressão ou dimensões do modelo.")
    if before["formulas"] != after["formulas"]:
        raise ValueError("A exportação alterou fórmulas existentes no modelo.")


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
