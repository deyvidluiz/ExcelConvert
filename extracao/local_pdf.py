"""Extração local de PDFs digitais: valores, geometria e função visual sem IA.

Tudo o que é observável na página (posição, largura, altura, mesclagem, tamanho
de fonte, negrito) vira metadado do contrato de layout. Cor nunca é lida daqui:
a paleta de saída é decidida por ``exportacao.style_service``.
"""

from collections import Counter
from io import BytesIO
from pathlib import Path

EDGE_TOLERANCE = 1.5
LINE_TOLERANCE = 2.5
SEGMENT_GAP = 10.0


def extract_pdf_tables(file_source):
    """Extrai tabelas digitais com valores e geometria local, sem IA."""
    import pdfplumber

    source = file_source
    if isinstance(file_source, (bytes, bytearray)):
        source = BytesIO(bytes(file_source))
    elif isinstance(file_source, Path):
        source = str(file_source)

    pages = []
    with pdfplumber.open(source) as pdf:
        for page_number, page in enumerate(pdf.pages, start=1):
            tables, table_boxes = _page_tables(page)
            pages.append(
                {
                    "page_number": page_number,
                    "page_width": float(page.width),
                    "page_height": float(page.height),
                    "tables": tables,
                    "regions": _text_regions(page, table_boxes),
                    "alerts": [],
                }
            )
    return pages


def _page_tables(page):
    try:
        detected = page.find_tables() or []
    except Exception:
        detected = []
    tables = []
    boxes = []
    for table in detected:
        try:
            values = _normalise_rows(table.extract() or [])
        except Exception:
            values = []
        if not values:
            continue
        data = _table_with_geometry(table, values, page)
        if data:
            tables.append(data)
            boxes.append(table.bbox)
    if tables:
        return tables, boxes
    # PDFs sem linhas desenhadas: mantém valores, sem geometria confiável.
    try:
        raw_tables = page.extract_tables() or []
    except Exception:
        raw_tables = []
    for raw_table in raw_tables:
        values = _normalise_rows(raw_table)
        if values:
            tables.append(_table_without_geometry(values))
    return tables, boxes


def _normalise_rows(raw_rows):
    rows = [[_cell_text(value) for value in row] for row in raw_rows if row is not None]
    width = max((len(row) for row in rows), default=0)
    if not width:
        return []
    return [row + [None] * (width - len(row)) for row in rows]


def _cell_text(value):
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _unique_edges(values):
    edges = []
    for value in sorted(values):
        if not edges or abs(value - edges[-1]) > EDGE_TOLERANCE:
            edges.append(float(value))
    return edges


def _edge_index(edges, value):
    best = 0
    for index, edge in enumerate(edges):
        if abs(edge - value) < abs(edges[best] - value):
            best = index
    return best


def _table_with_geometry(table, values, page):
    rows = [row for row in getattr(table, "rows", []) or []]
    if not rows:
        return _table_without_geometry(values)

    x_edges = _unique_edges(
        [coord for row in rows for cell in (row.cells or []) if cell for coord in (cell[0], cell[2])]
    )
    y_edges = _unique_edges([coord for row in rows for coord in (row.bbox[1], row.bbox[3])])
    if len(x_edges) < 2 or len(y_edges) < 2:
        return _table_without_geometry(values)

    column_widths = [x_edges[index + 1] - x_edges[index] for index in range(len(x_edges) - 1)]
    row_heights = [y_edges[index + 1] - y_edges[index] for index in range(len(y_edges) - 1)]
    words = _word_index(page)

    grid = []
    for row_index, row in enumerate(rows):
        row_values = values[row_index] if row_index < len(values) else []
        cells = row.cells or []
        line = [None] * len(column_widths)
        for position, box in enumerate(cells):
            if box is None:
                continue
            start_col = _edge_index(x_edges, box[0])
            end_col = _edge_index(x_edges, box[2])
            start_row = _edge_index(y_edges, box[1])
            end_row = _edge_index(y_edges, box[3])
            if start_col >= len(column_widths):
                continue
            value = row_values[position] if position < len(row_values) else None
            line[start_col] = {
                "value": value,
                "confidence": 1.0 if value is not None else None,
                "ambiguous": False,
                "review_reason": None,
                "col_span": max(1, end_col - start_col),
                "row_span": max(1, end_row - start_row),
                "x_position": float(box[0]),
                "y_position": float(box[1]),
                "width": float(box[2] - box[0]),
                "height": float(box[3] - box[1]),
                "border": {"top": "thin", "right": "thin", "bottom": "thin", "left": "thin", "confidence": 0.95},
                "style_evidence": _style_evidence(words, box),
            }
        grid.append(
            [
                cell if cell else {"value": None, "function": "empty", "ambiguous": False, "confidence": None}
                for cell in line
            ]
        )

    for row_index, function in enumerate(_row_functions(grid, len(column_widths))):
        for col_index, cell in enumerate(grid[row_index]):
            cell["row_index"] = row_index
            cell["col_index"] = col_index
            cell["function"] = "empty" if cell.get("value") is None else function

    bbox = getattr(table, "bbox", None) or (x_edges[0], y_edges[0], x_edges[-1], y_edges[-1])
    return {
        "title": None,
        "section_type": "data",
        "headers": grid[0],
        "rows": grid[1:],
        "merged_cells": [],
        "alerts": [],
        "has_borders": True,
        "x": float(bbox[0]),
        "y": float(bbox[1]),
        "width": float(bbox[2] - bbox[0]),
        "height": float(bbox[3] - bbox[1]),
        "column_widths": column_widths,
        "row_heights": row_heights,
    }


def _row_functions(grid, column_count):
    """Faixas largas de uma célula só são subtítulos; o primeiro bloco de
    colunas com vários rótulos é o cabeçalho da tabela."""
    functions = []
    header_seen = False
    for line in grid:
        if _is_band(line, column_count):
            functions.append("subheader")
            continue
        if not header_seen:
            header_seen = True
            functions.append("header")
            continue
        functions.append("data")
    return functions


def _is_band(line, column_count):
    filled = [cell for cell in line if cell and cell.get("value") is not None]
    return len(filled) == 1 and filled[0].get("col_span", 1) >= max(2, column_count - 1)


def _table_without_geometry(values):
    headers = [
        {"value": value, "function": "header", "ambiguous": False, "confidence": 1.0 if value else None, "col_index": index}
        for index, value in enumerate(values[0])
    ]
    rows = [
        [
            {
                "value": value,
                "function": "data" if value is not None else "empty",
                "ambiguous": False,
                "confidence": 1.0 if value is not None else None,
                "row_index": row_index,
                "col_index": col_index,
            }
            for col_index, value in enumerate(row)
        ]
        for row_index, row in enumerate(values[1:])
    ]
    return {
        "title": None,
        "section_type": "data",
        "headers": headers,
        "rows": rows,
        "merged_cells": [],
        "alerts": [],
        "has_borders": False,
    }


def _word_index(page):
    """Agrupa palavras em faixas horizontais para consultas por retângulo."""
    try:
        words = page.extract_words(extra_attrs=["size", "fontname"]) or []
    except Exception:
        return {}
    index = {}
    for word in words:
        top = word.get("top")
        if top is None:
            continue
        index.setdefault(int(top // 10), []).append(word)
    return index


def _words_in(words, box):
    x0, top, x1, bottom = box
    found = []
    for bucket in range(int(top // 10) - 1, int(bottom // 10) + 2):
        for word in words.get(bucket, ()):
            if word["x0"] >= x0 - 1 and word["x1"] <= x1 + 1 and word["top"] >= top - 1 and word["bottom"] <= bottom + 1:
                found.append(word)
    return found


def _style_evidence(words, box):
    found = _words_in(words, box)
    if not found:
        return None
    sizes = [word.get("size") for word in found if word.get("size")]
    fonts = [str(word.get("fontname") or "") for word in found]
    return {
        "font_size": round(float(Counter(sizes).most_common(1)[0][0]), 2) if sizes else None,
        "bold": bool(fonts) and all("bold" in name.lower() for name in fonts),
        "italic": bool(fonts) and all("italic" in name.lower() or "oblique" in name.lower() for name in fonts),
        "confidence": 0.9,
        "source": "pdf",
    }


def _inside_any(word, boxes):
    centre_x = (word["x0"] + word["x1"]) / 2
    centre_y = (word["top"] + word["bottom"]) / 2
    return any(x0 <= centre_x <= x1 and top <= centre_y <= bottom for x0, top, x1, bottom in boxes)


def _text_regions(page, table_boxes):
    """Texto fora das tabelas vira região com função inferida pelo tamanho da fonte."""
    try:
        words = page.extract_words(extra_attrs=["size", "fontname"]) or []
    except Exception:
        return []
    words = [word for word in words if (word.get("text") or "").strip() and not _inside_any(word, table_boxes)]
    if not words:
        return []

    sizes = [round(float(word.get("size") or 0), 1) for word in words if word.get("size")]
    body_size = Counter(sizes).most_common(1)[0][0] if sizes else 0
    max_size = max(sizes) if sizes else 0

    regions = []
    for line in _group_lines(words):
        for segment in _split_segments(line):
            regions.append(_region_from_segment(segment, body_size, max_size))
    return regions


def _group_lines(words):
    lines = []
    for word in sorted(words, key=lambda item: (round(item["top"], 1), item["x0"])):
        if lines and abs(lines[-1][-1]["top"] - word["top"]) <= LINE_TOLERANCE:
            lines[-1].append(word)
        else:
            lines.append([word])
    return [sorted(line, key=lambda item: item["x0"]) for line in lines]


def _split_segments(line):
    segments = [[line[0]]]
    for word in line[1:]:
        if word["x0"] - segments[-1][-1]["x1"] > SEGMENT_GAP:
            segments.append([word])
        else:
            segments[-1].append(word)
    return segments


def _region_from_segment(segment, body_size, max_size):
    size = round(float(Counter(round(float(word.get("size") or 0), 1) for word in segment).most_common(1)[0][0]), 1)
    bold = all("bold" in str(word.get("fontname") or "").lower() for word in segment)
    if max_size and size >= max_size - 0.1 and size > body_size:
        function = "title"
    elif size > body_size or bold:
        function = "subheader"
    else:
        function = "data"
    x0 = min(word["x0"] for word in segment)
    x1 = max(word["x1"] for word in segment)
    top = min(word["top"] for word in segment)
    bottom = max(word["bottom"] for word in segment)
    return {
        "value": " ".join((word.get("text") or "").strip() for word in segment).strip(),
        "function": function,
        "confidence": 1.0,
        "ambiguous": False,
        "x": float(x0),
        "y": float(top),
        "width": float(x1 - x0),
        "height": float(bottom - top),
        "style_evidence": {"font_size": size or None, "bold": bold, "confidence": 0.9, "source": "pdf"},
    }
