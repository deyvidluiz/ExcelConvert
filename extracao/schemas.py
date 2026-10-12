from typing import Optional

from pydantic import BaseModel, Field


class CellData(BaseModel):
    value: Optional[str] = None
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    ambiguous: bool = False
    review_reason: Optional[str] = None


class TableData(BaseModel):
    title: Optional[str] = None
    headers: list[CellData] = Field(default_factory=list)
    rows: list[list[CellData]] = Field(default_factory=list)
    merged_cells: list[str] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)


class PageData(BaseModel):
    page_number: int = Field(ge=1)
    tables: list[TableData] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)


class DocumentExtraction(BaseModel):
    document_name: Optional[str] = None
    pages: list[PageData] = Field(default_factory=list)
    alerts: list[str] = Field(default_factory=list)


def payload_from_model(model: DocumentExtraction) -> dict:
    return model.model_dump(mode="json")


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
        pages.append(
            {
                "page_number": page_number,
                "tables": [
                    {
                        "title": section,
                        "headers": [{"value": "Campo", "field_id": None}, {"value": "Valor", "field_id": None}],
                        "rows": [[{"value": item["name"], "field_id": item["field_id"]}, {**item, "value": item["value"]}] for item in items],
                        "merged_cells": [],
                        "alerts": [],
                    }
                    for section, items in sections.items()
                ],
                "alerts": [],
            }
        )
    return {
        "document_name": None,
        "template_code": model.template_code,
        "template_version": model.template_version,
        "template_fields": values,
        "pages": pages,
        "alerts": model.alerts,
    }
