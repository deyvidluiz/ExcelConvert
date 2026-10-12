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
