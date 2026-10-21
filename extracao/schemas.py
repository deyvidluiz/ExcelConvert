"""Contrato único de layout compartilhado por extração, revisão e exportação.

O mesmo payload descreve posição, função visual, mesclagem, bordas e dimensões
relativas das células. Cores nunca fazem parte do contrato: a saída recebe cor
de uma política externa (``exportacao.style_service``).
"""

import copy
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


LAYOUT_SCHEMA_VERSION = "3"
LAYOUT_CACHE_VERSION = f"layout-{LAYOUT_SCHEMA_VERSION}"


class CellFunction(str, Enum):
    TITLE = "title"
    HEADER = "header"
    SUBHEADER = "subheader"
    DATA = "data"
    REVIEW = "review"
    FOOTER = "footer"
    EMPTY = "empty"


class AlignmentType(str, Enum):
    LEFT = "left"
    CENTER = "center"
    RIGHT = "right"
    GENERAL = "general"


class BorderMetadata(BaseModel):
    top: Optional[str] = None
    right: Optional[str] = None
    bottom: Optional[str] = None
    left: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)


class StyleEvidence(BaseModel):
    """Indícios de estilo observados na origem; nunca define cor de saída."""

    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    font_size: Optional[float] = None
    bold: Optional[bool] = None
    italic: Optional[bool] = None
    source: Optional[str] = None


class MergedRange(BaseModel):
    """Mesclagem relativa à tabela: linha 0 é a linha de cabeçalho."""

    start_row: int = Field(default=0, ge=0)
    start_col: int = Field(default=0, ge=0)
    end_row: int = Field(default=0, ge=0)
    end_col: int = Field(default=0, ge=0)


class CellData(BaseModel):
    value: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    ambiguous: bool = False
    review_reason: Optional[str] = None
    function: Optional[CellFunction] = None
    alignment: Optional[AlignmentType] = None
    section_type: Optional[str] = None
    row_index: Optional[int] = Field(default=None, ge=0)
    col_index: Optional[int] = Field(default=None, ge=0)
    row_span: int = Field(default=1, ge=1)
    col_span: int = Field(default=1, ge=1)
    x_position: Optional[float] = None
    y_position: Optional[float] = None
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    border: Optional[BorderMetadata] = None
    style_evidence: Optional[StyleEvidence] = None
    field_id: Optional[str] = None


class RegionData(BaseModel):
    """Texto fora de tabelas: títulos, rótulos de seção, rodapés e assinaturas."""

    value: Optional[str] = None
    function: Optional[CellFunction] = None
    alignment: Optional[AlignmentType] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    ambiguous: bool = False
    review_reason: Optional[str] = None
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    style_evidence: Optional[StyleEvidence] = None


class TableData(BaseModel):
    title: Optional[str] = None
    section_type: Optional[str] = None
    headers: list[CellData] = Field(default_factory=list)
    rows: list[list[CellData]] = Field(default_factory=list)
    merged_cells: list[MergedRange] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    has_borders: bool = True
    x: Optional[float] = None
    y: Optional[float] = None
    width: Optional[float] = Field(default=None, ge=0)
    height: Optional[float] = Field(default=None, ge=0)
    column_widths: Optional[list[float]] = None
    row_heights: Optional[list[float]] = None
    column_widths_relative: Optional[list[float]] = None
    row_heights_relative: Optional[list[float]] = None


class PageData(BaseModel):
    page_number: int = Field(ge=1)
    tables: list[TableData] = Field(default_factory=list)
    regions: list[RegionData] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    page_width: Optional[float] = None
    page_height: Optional[float] = None


class DocumentExtraction(BaseModel):
    document_name: Optional[str] = None
    document_type: Optional[str] = None
    pages: list[PageData] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)
    schema_version: str = LAYOUT_SCHEMA_VERSION
    layout_version: str = LAYOUT_SCHEMA_VERSION


def payload_from_model(model: DocumentExtraction) -> dict:
    return normalise_layout_payload(model.model_dump(mode="json"))


_FUNCTION_VALUES = {item.value for item in CellFunction}
_ALIGNMENT_VALUES = {item.value for item in AlignmentType}


def _clean_function(value, default):
    value = getattr(value, "value", value)
    return value if value in _FUNCTION_VALUES else default


def _clean_alignment(value):
    value = getattr(value, "value", value)
    return value if value in _ALIGNMENT_VALUES else None


def _positive_int(value, default=1):
    try:
        result = int(value)
    except (TypeError, ValueError):
        return default
    return result if result >= 1 else default


def _normalise_cell(cell, *, function, row_index=None, col_index=None, section_type=None):
    result = dict(cell) if isinstance(cell, dict) else {"value": cell}
    if result.get("value") is not None and not isinstance(result["value"], str):
        result["value"] = str(result["value"])
    result["ambiguous"] = bool(result.get("ambiguous"))
    default = function.value if isinstance(function, CellFunction) else function
    result["function"] = _clean_function(result.get("function"), default)
    if result["ambiguous"] and result["function"] == CellFunction.DATA.value:
        result["function"] = CellFunction.REVIEW.value
    result["alignment"] = _clean_alignment(result.get("alignment"))
    if result.get("row_index") is None:
        result["row_index"] = row_index
    if result.get("col_index") is None:
        result["col_index"] = col_index
    if not result.get("section_type"):
        result["section_type"] = section_type
    result["row_span"] = _positive_int(result.get("row_span"))
    result["col_span"] = _positive_int(result.get("col_span"))
    return result


def _normalise_region(region):
    if not isinstance(region, dict):
        region = {"value": region}
    result = dict(region)
    # Payloads antigos do extrator local gravavam o texto em "text".
    if result.get("value") is None and result.get("text") is not None:
        result["value"] = result.pop("text")
    if result.get("value") is not None and not isinstance(result["value"], str):
        result["value"] = str(result["value"])
    result["ambiguous"] = bool(result.get("ambiguous"))
    default = CellFunction.REVIEW.value if result["ambiguous"] else CellFunction.DATA.value
    result["function"] = _clean_function(result.get("function"), default)
    result["alignment"] = _clean_alignment(result.get("alignment"))
    return result


def _normalise_merge(merged):
    """Aceita o formato relativo novo e os formatos antigos (string/absoluto)."""
    if isinstance(merged, str):
        return {"ref": merged, "basis": "sheet"}
    if not isinstance(merged, dict):
        return None
    if merged.get("ref"):
        return {"ref": str(merged["ref"]), "basis": merged.get("basis") or "sheet"}
    keys = ("start_row", "start_col", "end_row", "end_col")
    aliases = {"start_col": "start_column", "end_col": "end_column"}
    values = {}
    for key in keys:
        raw = merged.get(key, merged.get(aliases.get(key, key)))
        try:
            values[key] = int(raw)
        except (TypeError, ValueError):
            return None
    basis = merged.get("basis")
    values["basis"] = basis if basis in {"table", "sheet"} else "table"
    if values["end_row"] < values["start_row"] or values["end_col"] < values["start_col"]:
        return None
    if values["start_row"] == values["end_row"] and values["start_col"] == values["end_col"]:
        return None
    return values


def _column_count(table):
    return max(
        len(table.get("headers", [])),
        max((len(row) for row in table.get("rows", [])), default=0),
        1,
    )


def _derive_column_weights(table, column_count):
    weights = []
    for col_index in range(column_count):
        values = []
        if col_index < len(table["headers"]):
            values.append(table["headers"][col_index].get("value"))
        values.extend(row[col_index].get("value") if col_index < len(row) else None for row in table["rows"])
        length = max((len(str(value)) for value in values if value is not None), default=8)
        weights.append(max(8, min(42, length + 2)))
    return weights


def normalise_layout_payload(payload: Optional[dict]) -> dict:
    """Adapta payloads antigos e novos ao contrato compartilhado de layout."""
    result = copy.deepcopy(payload or {})
    result.setdefault("document_name", None)
    result.setdefault("pages", [])
    result.setdefault("alerts", [])
    result["schema_version"] = LAYOUT_SCHEMA_VERSION
    result["layout_version"] = LAYOUT_SCHEMA_VERSION

    if not isinstance(result.get("pages"), list):
        result["pages"] = []

    for page in result["pages"]:
        page.setdefault("tables", [])
        page.setdefault("alerts", [])
        page["regions"] = [_normalise_region(region) for region in page.get("regions") or []]
        for table in page["tables"]:
            table.setdefault("headers", [])
            table.setdefault("rows", [])
            table.setdefault("alerts", [])
            table["has_borders"] = bool(table.get("has_borders", True))
            section_type = table.get("section_type") or "data"
            table["section_type"] = section_type
            table["headers"] = [
                _normalise_cell(cell, function=CellFunction.HEADER, row_index=0, col_index=index, section_type=section_type)
                for index, cell in enumerate(table["headers"])
            ]
            table["rows"] = [
                [
                    _normalise_cell(
                        cell,
                        function=CellFunction.DATA,
                        row_index=row_index,
                        col_index=col_index,
                        section_type=section_type,
                    )
                    for col_index, cell in enumerate(row)
                ]
                for row_index, row in enumerate(table["rows"])
            ]
            merges = (_normalise_merge(item) for item in table.get("merged_cells") or [])
            table["merged_cells"] = [item for item in merges if item]
            column_count = _column_count(table)
            if not table.get("column_widths") and not table.get("column_widths_relative"):
                table["column_widths_relative"] = _derive_column_weights(table, column_count)
            if not table.get("row_heights") and not table.get("row_heights_relative"):
                # Índice 0 é a linha de cabeçalho, igual a column_widths para colunas.
                table["row_heights_relative"] = [
                    max(1, min(4, max((str(cell.get("value") or "").count("\n") + 1 for cell in row), default=1)))
                    for row in [table["headers"], *table["rows"]]
                ]
    return result


def has_geometry(payload: dict) -> bool:
    """Informa se há coordenadas suficientes para reconstruir a folha original."""
    for page in payload.get("pages", []):
        if not (page.get("page_width") and page.get("page_height")):
            continue
        for table in page.get("tables", []):
            if table.get("x") is not None and table.get("y") is not None and table.get("column_widths"):
                return True
        for region in page.get("regions", []):
            if region.get("x") is not None and region.get("y") is not None:
                return True
    return False


class TemplateFieldValue(BaseModel):
    field_id: str
    page_number: int = Field(ge=1)
    value: Optional[str] = None
    observed_unit: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    ambiguous: bool = False
    review_reason: Optional[str] = None


class TemplateExtraction(BaseModel):
    template_code: str
    template_version: str
    fields: list[TemplateFieldValue] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)


def template_payload_from_model(model: TemplateExtraction, template) -> dict:
    known = {field.field_id: field for field in template.fields.all()}
    values = []
    for item in model.fields:
        definition = known.get(item.field_id)
        values.append(
            {
                "field_id": item.field_id,
                "name": definition.name if definition else item.field_id,
                "section": definition.section if definition else "Revisar",
                "page_number": item.page_number,
                "value": item.value,
                "observed_unit": item.observed_unit,
                "confidence": item.confidence,
                "ambiguous": item.ambiguous,
                "review_reason": item.review_reason,
                "excel_sheet": definition.excel_sheet if definition else "",
                "excel_cell": definition.excel_cell if definition else "",
                "excel_range": definition.excel_range if definition else "",
                "expected_type": definition.expected_type if definition else "text",
                "required": definition.required if definition else False,
            }
        )
    values_by_page = {}
    for value in values:
        values_by_page.setdefault(value["page_number"], []).append(value)
    pages = []
    for page_number in sorted(values_by_page):
        sections = {}
        for value in values_by_page[page_number]:
            sections.setdefault(value["section"], []).append(value)
        tables = []
        for section, items in sections.items():
            tables.append(
                {
                    "title": section,
                    "section_type": "subheader",
                    "headers": [
                        {"value": "Campo", "function": "header"},
                        {"value": "Valor", "function": "header"},
                    ],
                    "rows": [
                        [
                            {"value": item["name"], "field_id": item["field_id"], "function": "subheader"},
                            {
                                **item,
                                "value": item["value"],
                                "function": "review" if item["ambiguous"] else "data",
                            },
                        ]
                        for item in items
                    ],
                    "merged_cells": [],
                    "alerts": [],
                    "has_borders": True,
                }
            )
        pages.append({"page_number": page_number, "tables": tables, "alerts": []})
    return normalise_layout_payload(
        {
            "document_name": None,
            "template_code": model.template_code,
            "template_version": model.template_version,
            "template_fields": values,
            "pages": pages,
            "alerts": model.alerts,
        }
    )
