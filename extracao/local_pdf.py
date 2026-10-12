def extract_pdf_tables(file_path):
    """Tenta extrair tabelas de PDFs digitais sem chamar a IA."""
    import pdfplumber

    pages = []
    with pdfplumber.open(file_path) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables = []
            for raw_table in page.extract_tables() or []:
                if not raw_table:
                    continue
                normalized = [[_cell(value) for value in row] for row in raw_table]
                width = max((len(row) for row in normalized), default=0)
                if not width:
                    continue
                normalized = [row + [None] * (width - len(row)) for row in normalized]
                tables.append(
                    {
                        "title": None,
                        "headers": [_cell_data(value) for value in normalized[0]],
                        "rows": [[_cell_data(value) for value in row] for row in normalized[1:]],
                        "merged_cells": [],
                        "alerts": [],
                    }
                )
            pages.append({"page_number": page_number, "tables": tables, "alerts": []})
    return pages


def _cell(value):
    if value is None:
        return None
    text = str(value)
    return text if text.strip() else None


def _cell_data(value):
    return {"value": value, "confidence": 1.0 if value is not None else None, "ambiguous": False, "review_reason": None}
