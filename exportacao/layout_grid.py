"""Transforma uma página do contrato de layout numa grade de planilha.

Cada página vira uma única folha. Quando há geometria (PDF digital ou extração
visual com posições), as tabelas e os textos soltos são encaixados numa grade
de colunas e linhas comum, preservando ordem, mesclagem e proporções. Sem
geometria, cai numa apresentação padrão em blocos empilhados.
"""

import bisect
from dataclasses import dataclass, field

from extracao.schemas import CellFunction

MAX_COLUMNS = 160
MAX_ROWS = 900
COLUMN_TOLERANCE = 2.0
ROW_TOLERANCE = 1.5
POINTS_PER_WIDTH_UNIT = 5.4
MIN_COLUMN_WIDTH = 1.2
MAX_COLUMN_WIDTH = 60.0
MIN_ROW_HEIGHT = 8.0
MAX_ROW_HEIGHT = 200.0


@dataclass
class PlacedCell:
    row: int
    col: int
    value: object = None
    function: str = CellFunction.DATA.value
    row_span: int = 1
    col_span: int = 1
    metadata: dict = field(default_factory=dict)


@dataclass
class SheetPlan:
    title: str
    cells: list = field(default_factory=list)
    merges: list = field(default_factory=list)
    column_widths: dict = field(default_factory=dict)
    row_heights: dict = field(default_factory=dict)
    freeze_panes: str = None
    landscape: bool = False
    geometric: bool = False


def plan_page(page, index=1):
    plan = _plan_geometric(page, index) if page_has_geometry(page) else None
    if plan is None:
        plan = _plan_sequential(page, index)
    width = page.get("page_width") or 0
    height = page.get("page_height") or 0
    plan.landscape = bool(width and height and width > height)
    return plan


def page_has_geometry(page):
    if not (page.get("page_width") and page.get("page_height")):
        return False
    for table in page.get("tables", []):
        if table.get("x") is not None and table.get("y") is not None and table.get("column_widths"):
            return True
    for region in page.get("regions", []):
        if region.get("x") is not None and region.get("y") is not None:
            return True
    return False


# --------------------------------------------------------------------------- #
# grade
# --------------------------------------------------------------------------- #


def _cluster(values, tolerance):
    edges = []
    for value in sorted(float(value) for value in values):
        if edges and value - edges[-1][0] <= tolerance:
            edges[-1].append(value)
        else:
            edges.append([value])
    return [sum(group) / len(group) for group in edges]


def _limit(edges, maximum):
    """Funde as faixas mais estreitas até caber no limite prático da planilha."""
    while len(edges) - 1 > maximum and len(edges) > 2:
        gaps = [(edges[index + 1] - edges[index], index) for index in range(len(edges) - 1)]
        _, narrowest = min(gaps)
        edges.pop(narrowest + 1 if narrowest + 1 < len(edges) - 1 else narrowest)
    return edges


def _index_of(edges, value):
    position = bisect.bisect_left(edges, value)
    candidates = [index for index in (position - 1, position) if 0 <= index < len(edges)]
    if not candidates:
        return 0
    return min(candidates, key=lambda index: abs(edges[index] - value))


def _scaled(values, total, count):
    if not values:
        return None
    numbers = [max(0.0, float(value or 0)) for value in values][:count]
    numbers += [0.0] * max(0, count - len(numbers))
    sum_values = sum(numbers)
    if not sum_values:
        return None
    if not total:
        return numbers
    return [value * total / sum_values for value in numbers]


def _column_edges(table):
    x = table.get("x")
    if x is None:
        return None
    count = _column_count(table)
    widths = table.get("column_widths")
    if not widths:
        widths = _scaled(table.get("column_widths_relative"), table.get("width"), count)
    if not widths:
        return None
    edges = [float(x)]
    for width in widths[:count]:
        edges.append(edges[-1] + max(0.0, float(width or 0)))
    return edges


def _row_edges(table):
    y = table.get("y")
    if y is None:
        return None
    count = len(table.get("rows", [])) + 1
    heights = table.get("row_heights")
    if not heights:
        heights = _scaled(table.get("row_heights_relative"), table.get("height"), count)
    if not heights:
        return None
    edges = [float(y)]
    for height in heights[:count]:
        edges.append(edges[-1] + max(0.0, float(height or 0)))
    return edges


def _column_count(table):
    return max(
        len(table.get("headers", [])),
        max((len(row) for row in table.get("rows", [])), default=0),
        1,
    )


def _plan_geometric(page, index):
    tables = []
    leftovers = []
    column_values = []
    row_values = []
    for table in page.get("tables", []):
        columns = _column_edges(table)
        rows = _row_edges(table)
        if not columns or not rows:
            leftovers.append(table)
            continue
        tables.append((table, columns, rows))
        column_values.extend(columns)
        row_values.extend(rows)

    regions = [
        region
        for region in page.get("regions", [])
        if region.get("x") is not None and region.get("y") is not None and (region.get("value") or "").strip()
    ]
    for region in regions:
        x = float(region["x"])
        y = float(region["y"])
        column_values.extend([x, x + float(region.get("width") or 0)])
        row_values.extend([y, y + max(10.0, float(region.get("height") or 0))])

    if not tables and not regions:
        return None

    column_edges = _limit(_cluster(column_values, COLUMN_TOLERANCE), MAX_COLUMNS)
    row_edges = _limit(_cluster(row_values, ROW_TOLERANCE), MAX_ROWS)
    if len(column_edges) < 2 or len(row_edges) < 2:
        return None

    plan = SheetPlan(title=_sheet_title(page, index), geometric=True)
    occupied = set()
    declared = []

    for table, columns, rows in tables:
        has_borders = bool(table.get("has_borders", True))
        grid = [table.get("headers", []), *table.get("rows", [])]
        for row_index, line in enumerate(grid):
            for col_index, cell in enumerate(line):
                placed = _place_table_cell(
                    cell,
                    row_index=row_index,
                    col_index=col_index,
                    columns=columns,
                    rows=rows,
                    column_edges=column_edges,
                    row_edges=row_edges,
                    has_borders=has_borders,
                )
                if placed and _claim(occupied, placed):
                    plan.cells.append(placed)
        _add_declared_merges(declared, table, columns, rows, column_edges, row_edges)

    for region in regions:
        placed = _place_region(region, column_edges, row_edges)
        if placed and _claim(occupied, placed):
            plan.cells.append(placed)

    for index_, _ in enumerate(column_edges[:-1]):
        points = column_edges[index_ + 1] - column_edges[index_]
        plan.column_widths[index_ + 1] = _clamp(points / POINTS_PER_WIDTH_UNIT, MIN_COLUMN_WIDTH, MAX_COLUMN_WIDTH)
    for index_, _ in enumerate(row_edges[:-1]):
        points = row_edges[index_ + 1] - row_edges[index_]
        plan.row_heights[index_ + 1] = _clamp(points, MIN_ROW_HEIGHT, MAX_ROW_HEIGHT)

    loose_regions = [
        region
        for region in page.get("regions", [])
        if (region.get("x") is None or region.get("y") is None) and (region.get("value") or "").strip()
    ]
    _append_leftovers(plan, leftovers, loose_regions, len(row_edges), len(column_edges) - 1)
    plan.merges = _merges_from_cells(plan.cells) + declared
    return plan


def _append_leftovers(plan, leftovers, loose_regions, grid_rows, grid_columns):
    """Tabelas e textos sem geometria não podem sumir: entram abaixo da grade."""
    if not leftovers and not loose_regions:
        return
    widths = dict(plan.column_widths)
    cursor = grid_rows + 2
    for table in leftovers:
        cursor, _ = _write_table_block(plan, table, cursor)
    _write_regions(plan, loose_regions, cursor, grid_columns)
    plan.column_widths = widths


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, float(value)))


def _claim(occupied, placed):
    coordinates = {
        (placed.row + row, placed.col + col)
        for row in range(placed.row_span)
        for col in range(placed.col_span)
    }
    if coordinates & occupied:
        return False
    occupied |= coordinates
    return True


def _place_table_cell(cell, *, row_index, col_index, columns, rows, column_edges, row_edges, has_borders):
    if not isinstance(cell, dict):
        cell = {"value": cell}
    col_span = max(1, int(cell.get("col_span") or 1))
    row_span = max(1, int(cell.get("row_span") or 1))

    left = cell.get("x_position")
    if left is None:
        left = columns[min(col_index, len(columns) - 1)]
    width = cell.get("width")
    right = left + float(width) if width else columns[min(col_index + col_span, len(columns) - 1)]

    top = cell.get("y_position")
    if top is None:
        top = rows[min(row_index, len(rows) - 1)]
    height = cell.get("height")
    bottom = top + float(height) if height else rows[min(row_index + row_span, len(rows) - 1)]

    start_col = _index_of(column_edges, float(left))
    end_col = _index_of(column_edges, float(right))
    start_row = _index_of(row_edges, float(top))
    end_row = _index_of(row_edges, float(bottom))
    if start_col >= len(column_edges) - 1 or start_row >= len(row_edges) - 1:
        return None

    return PlacedCell(
        row=start_row + 1,
        col=start_col + 1,
        value=cell.get("value"),
        function=cell.get("function") or CellFunction.DATA.value,
        row_span=max(1, min(end_row - start_row, len(row_edges) - 1 - start_row)),
        col_span=max(1, min(end_col - start_col, len(column_edges) - 1 - start_col)),
        metadata=_metadata(cell, has_borders),
    )


def _place_region(region, column_edges, row_edges):
    left = float(region["x"])
    right = left + float(region.get("width") or 0)
    top = float(region["y"])
    bottom = top + max(10.0, float(region.get("height") or 0))
    start_col = _index_of(column_edges, left)
    end_col = _index_of(column_edges, right)
    start_row = _index_of(row_edges, top)
    end_row = _index_of(row_edges, bottom)
    if start_col >= len(column_edges) - 1 or start_row >= len(row_edges) - 1:
        return None
    return PlacedCell(
        row=start_row + 1,
        col=start_col + 1,
        value=region.get("value"),
        function=region.get("function") or CellFunction.DATA.value,
        row_span=max(1, min(end_row - start_row, len(row_edges) - 1 - start_row)),
        col_span=max(1, min(end_col - start_col, len(column_edges) - 1 - start_col)),
        metadata=_metadata(region, has_borders=False),
    )


def _metadata(source, has_borders):
    return {
        "alignment": source.get("alignment"),
        "border": source.get("border"),
        "style_evidence": source.get("style_evidence"),
        "has_borders": has_borders,
    }


def _add_declared_merges(declared, table, columns, rows, column_edges, row_edges):
    """Mesclagens informadas no payload (Gemini ou payloads antigos)."""
    for merged in table.get("merged_cells", []):
        if merged.get("basis") != "table":
            continue
        start_row = _index_of(row_edges, rows[min(int(merged["start_row"]), len(rows) - 1)])
        end_row = _index_of(row_edges, rows[min(int(merged["end_row"]) + 1, len(rows) - 1)])
        start_col = _index_of(column_edges, columns[min(int(merged["start_col"]), len(columns) - 1)])
        end_col = _index_of(column_edges, columns[min(int(merged["end_col"]) + 1, len(columns) - 1)])
        if end_row > start_row or end_col > start_col:
            declared.append((start_row + 1, start_col + 1, end_row, end_col))


def _merges_from_cells(cells):
    return [
        (cell.row, cell.col, cell.row + cell.row_span - 1, cell.col + cell.col_span - 1)
        for cell in cells
        if cell.row_span > 1 or cell.col_span > 1
    ]


def _sheet_title(page, index):
    return f"Página {page.get('page_number', index)}"


# --------------------------------------------------------------------------- #
# apresentação padrão (sem geometria)
# --------------------------------------------------------------------------- #

TITLE_ROW_HEIGHT = 24
HEADER_ROW_HEIGHT = 30


def _sequential_widths(table, count):
    values = table.get("column_widths_relative") or table.get("column_widths")
    if not values:
        return [12.0] * count
    values = list(values)[:count] + [1.0] * max(0, count - len(values))
    total = sum(float(value or 0) for value in values) or count
    return [_clamp(82 * float(value or 1) / total, 6, MAX_COLUMN_WIDTH) for value in values]


def _sequential_height(table, row_index, row):
    heights = table.get("row_heights_relative") or table.get("row_heights") or []
    if row_index < len(heights) and heights[row_index]:
        return _clamp(float(heights[row_index]) * 18, 15, 120)
    lines = max((str(_cell_value(cell) or "").count("\n") + 1 for cell in row), default=1)
    return 18 + min(4, lines - 1) * 12


def _cell_value(cell):
    return cell.get("value") if isinstance(cell, dict) else cell


def _plan_sequential(page, index):
    """Apresentação padrão: blocos empilhados numa folha por página."""
    plan = SheetPlan(title=_sheet_title(page, index))
    tables = page.get("tables", [])
    regions = [region for region in page.get("regions", []) if (region.get("value") or "").strip()]
    page_width = max((_column_count(table) for table in tables), default=1)

    leading = [region for region in regions if region.get("function") != CellFunction.FOOTER.value]
    trailing = [region for region in regions if region.get("function") == CellFunction.FOOTER.value]

    cursor = 1
    if not leading and not any(table.get("title") for table in tables):
        # Sem título algum, mantém o cabeçalho da apresentação antiga.
        cursor = _write_banner(plan, f"Página {page.get('page_number', index)}", cursor, page_width)
    cursor = _write_regions(plan, leading, cursor, page_width)

    first_header_row = None
    for table in tables:
        cursor, header_row = _write_table_block(plan, table, cursor)
        if first_header_row is None and header_row:
            first_header_row = header_row

    _write_regions(plan, trailing, cursor, page_width)

    plan.merges = [item for item in plan.merges if item]
    plan.merges.extend(_merges_from_cells(plan.cells))
    if first_header_row and len(tables) == 1 and not leading:
        plan.freeze_panes = f"A{first_header_row + 1}"
    return plan


def _write_banner(plan, text, cursor, width, function=CellFunction.TITLE.value):
    plan.cells.append(
        PlacedCell(
            row=cursor,
            col=1,
            value=text,
            function=function,
            col_span=max(1, width),
            metadata={"has_borders": True, "alignment": "left"},
        )
    )
    plan.row_heights[cursor] = TITLE_ROW_HEIGHT
    return cursor + 2


def _write_regions(plan, regions, cursor, width):
    for region in regions:
        plan.cells.append(
            PlacedCell(
                row=cursor,
                col=1,
                value=region.get("value"),
                function=region.get("function") or CellFunction.DATA.value,
                col_span=max(1, width),
                metadata=_metadata(region, has_borders=False),
            )
        )
        plan.row_heights[cursor] = TITLE_ROW_HEIGHT if region.get("function") == CellFunction.TITLE.value else 18
        cursor += 1
    return cursor + 1 if regions else cursor


def _write_table_block(plan, table, cursor):
    """Escreve título, cabeçalho e linhas de uma tabela a partir de `cursor`."""
    count = _column_count(table)
    has_borders = bool(table.get("has_borders", True))
    if table.get("title"):
        cursor = _write_banner(plan, table["title"], cursor, count)

    header_row = cursor
    headers = table.get("headers", [])
    for col_index, cell in enumerate(headers, start=1):
        plan.cells.append(_sequential_cell(cell, header_row, col_index, CellFunction.HEADER.value, has_borders))
    if headers:
        plan.row_heights[header_row] = HEADER_ROW_HEIGHT

    for row_offset, row in enumerate(table.get("rows", []), start=1):
        for col_index, cell in enumerate(row, start=1):
            plan.cells.append(
                _sequential_cell(cell, header_row + row_offset, col_index, CellFunction.DATA.value, has_borders)
            )
        plan.row_heights[header_row + row_offset] = _sequential_height(table, row_offset, row)

    for col_index, width in enumerate(_sequential_widths(table, count), start=1):
        plan.column_widths[col_index] = max(plan.column_widths.get(col_index, 0), width)

    for merged in table.get("merged_cells", []):
        plan.merges.append(_sequential_merge(merged, header_row))

    next_cursor = header_row + len(table.get("rows", [])) + 2
    return next_cursor, (header_row if headers else None)


def _sequential_cell(cell, row, col, default_function, has_borders):
    if not isinstance(cell, dict):
        cell = {"value": cell}
    return PlacedCell(
        row=row,
        col=col,
        value=cell.get("value"),
        function=cell.get("function") or default_function,
        row_span=max(1, int(cell.get("row_span") or 1)),
        col_span=max(1, int(cell.get("col_span") or 1)),
        metadata=_metadata(cell, has_borders),
    )


def _sequential_merge(merged, header_row):
    if merged.get("basis") == "sheet":
        return merged.get("ref") or (
            merged["start_row"],
            merged["start_col"],
            merged["end_row"],
            merged["end_col"],
        )
    if "start_row" not in merged:
        return None
    return (
        header_row + int(merged["start_row"]),
        int(merged["start_col"]) + 1,
        header_row + int(merged["end_row"]),
        int(merged["end_col"]) + 1,
    )
