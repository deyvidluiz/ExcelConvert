from io import BytesIO

import pytest
from openpyxl import load_workbook

from exportacao.services import build_docx, build_pdf, build_xlsx
from validacao.services import validate_payload


@pytest.fixture
def payload():
    return {"document_name": "dados.png", "pages": [{"page_number": 1, "tables": [{"title": "Financeiro", "headers": [{"value": "Código"}, {"value": "Valor"}, {"value": "Data"}], "rows": [[{"value": "0012"}, {"value": "R$ 10,50"}, {"value": "01/02/2026"}], [{"value": None}, {"value": "??", "ambiguous": True, "review_reason": "trecho ilegível"}, {"value": None}]], "merged_cells": [], "alerts": []}], "alerts": []}], "alerts": []}


def test_validacao_detecta_ambiguidade_e_preserva_vazio(payload):
    alerts = validate_payload(payload)
    assert any("revisão manual" in alert for alert in alerts)
    assert payload["pages"][0]["tables"][0]["rows"][0][0]["value"] == "0012"
    assert payload["pages"][0]["tables"][0]["rows"][1][0]["value"] is None


def test_exportacoes_sao_geradas(payload):
    xlsx = build_xlsx(payload)
    workbook = load_workbook(xlsx)
    assert workbook.active["A4"].value == "0012"
    assert build_docx(payload).getvalue()[:2] == b"PK"
    assert build_pdf(payload).getvalue().startswith(b"%PDF")
