from extracao.schemas import CellFunction, normalise_layout_payload


def validate_payload(payload):
    alerts = []
    for field in payload.get("template_fields", []):
        if field.get("ambiguous"):
            alerts.append(f"Campo {field.get('name') or field.get('field_id')}: leitura ambígua; confirme na imagem original.")
        if field.get("required") and field.get("value") in (None, ""):
            alerts.append(f"Campo obrigatório {field.get('name') or field.get('field_id')} está vazio.")
    for page in payload.get("pages", []):
        for table_index, table in enumerate(page.get("tables", []), start=1):
            headers = table.get("headers", [])
            width = len(headers)
            for row_index, row in enumerate(table.get("rows", []), start=1):
                if width and len(row) != width:
                    alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: linha {row_index} tem colunas inconsistentes.")
            if not headers and table.get("rows"):
                alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: cabeçalho não identificado.")
            if any(_ambiguous(cell) for cell in headers):
                alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: cabeçalho ambíguo.")
            if any(_ambiguous(cell) for row in table.get("rows", []) for cell in row):
                alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: existem células para revisão manual.")
    return alerts


def _ambiguous(cell):
    return isinstance(cell, dict) and bool(cell.get("ambiguous"))


def merge_reviewed_values(stored, submitted):
    """Aplica apenas os valores revisados sobre o layout já persistido.

    A revisão manual corrige texto; posição, mesclagem, função visual, bordas e
    dimensões continuam vindo da extração. Assim, salvar o editor nunca apaga os
    metadados de layout, mesmo que o navegador envie um payload reduzido.
    """
    result = normalise_layout_payload(stored)
    submitted = submitted if isinstance(submitted, dict) else {}

    submitted_pages = submitted.get("pages") or []
    for page_index, page in enumerate(result.get("pages", [])):
        submitted_page = submitted_pages[page_index] if page_index < len(submitted_pages) else {}
        _merge_line(page.get("regions", []), (submitted_page or {}).get("regions") or [])
        submitted_tables = (submitted_page or {}).get("tables") or []
        for table_index, table in enumerate(page.get("tables", [])):
            submitted_table = submitted_tables[table_index] if table_index < len(submitted_tables) else {}
            _merge_line(table.get("headers", []), (submitted_table or {}).get("headers") or [])
            submitted_rows = (submitted_table or {}).get("rows") or []
            for row_index, row in enumerate(table.get("rows", [])):
                _merge_line(row, submitted_rows[row_index] if row_index < len(submitted_rows) else [])

    stored_fields = result.get("template_fields")
    if isinstance(stored_fields, list):
        submitted_fields = {
            item.get("field_id"): item
            for item in submitted.get("template_fields") or []
            if isinstance(item, dict) and item.get("field_id")
        }
        for field in stored_fields:
            candidate = submitted_fields.get(field.get("field_id"))
            if candidate and "value" in candidate:
                field["value"] = _clean_value(candidate.get("value"))

    return normalise_layout_payload(result)


def _merge_line(cells, submitted_cells):
    for index, cell in enumerate(cells):
        if index >= len(submitted_cells):
            continue
        candidate = submitted_cells[index]
        if isinstance(candidate, dict):
            if "value" not in candidate:
                continue
            value = candidate.get("value")
        else:
            value = candidate
        value = _clean_value(value)
        if value != cell.get("value"):
            cell["value"] = value
            # Um valor corrigido manualmente deixa de ser leitura ambígua da IA.
            if cell.get("ambiguous"):
                cell["ambiguous"] = False
                cell["review_reason"] = None
                if cell.get("function") == CellFunction.REVIEW.value:
                    cell["function"] = CellFunction.DATA.value


def _clean_value(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None
