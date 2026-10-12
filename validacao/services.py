def validate_payload(payload):
    alerts = []
    for page in payload.get("pages", []):
        for table_index, table in enumerate(page.get("tables", []), start=1):
            width = len(table.get("headers", []))
            for row_index, row in enumerate(table.get("rows", []), start=1):
                if width and len(row) != width:
                    alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: linha {row_index} tem colunas inconsistentes.")
            if not table.get("headers") and table.get("rows"):
                alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: cabeçalho não identificado.")
            if any(cell.get("ambiguous") for cell in table.get("headers", [])):
                alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: cabeçalho ambíguo.")
            if any(cell.get("ambiguous") for row in table.get("rows", []) for cell in row):
                alerts.append(f"Página {page.get('page_number')}, tabela {table_index}: existem células para revisão manual.")
    return alerts
