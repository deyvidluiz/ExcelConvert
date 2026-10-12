import io

import fitz
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from documentos.models import Document, ExtractionCache
from extracao.gemini_service import GeminiExtractionError
from extracao.services import ExtractionService


def make_image():
    from PIL import Image

    image = Image.new("RGB", (100, 50), "white")
    out = io.BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def make_table_pdf():
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4)
    table = Table([["Código", "Valor"], ["0012", "R$ 10,50"], ["", ""]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    doc.build([table])
    return out.getvalue()


@pytest.mark.django_db
def test_pdf_digital_e_extraido_localmente(user, tmp_path):
    document = Document.objects.create(user=user, file=SimpleUploadedFile("tabela.pdf", make_table_pdf(), content_type="application/pdf"), original_name="tabela.pdf", mime_type="application/pdf", size_bytes=100, sha256="local-pdf")
    payload = ExtractionService().process(document)
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert document.token_count == 0
    assert payload["pages"][0]["tables"][0]["rows"][0][0]["value"] == "0012"
    assert ExtractionCache.objects.filter(source="local").exists()


@pytest.mark.django_db
def test_resposta_gemini_simulada_e_cache(user):
    document = Document.objects.create(user=user, file=SimpleUploadedFile("tabela.png", make_image(), content_type="image/png"), original_name="tabela.png", mime_type="image/png", size_bytes=100, sha256="same-image")

    class FakeExtractor:
        calls = 0

        def extract(self, **kwargs):
            self.calls += 1
            return {"document_name": "tabela.png", "pages": [{"page_number": 1, "tables": [{"headers": [{"value": "Código"}], "rows": [[{"value": "0012"}], [{"value": None}]], "merged_cells": [], "alerts": []}], "alerts": []}], "alerts": []}, 321

    fake = FakeExtractor()
    service = ExtractionService(fake)
    payload = service.process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert document.token_count == 321
    assert payload["pages"][0]["tables"][0]["rows"][0][0]["value"] == "0012"
    second = Document.objects.create(user=user, file=SimpleUploadedFile("copia.png", make_image(), content_type="image/png"), original_name="copia.png", mime_type="image/png", size_bytes=100, sha256="same-image")
    service.process(second, paid_confirmed=True)
    assert fake.calls == 1


@pytest.mark.django_db
def test_ia_sem_confirmacao_nao_e_chamada(user):
    document = Document.objects.create(user=user, file=SimpleUploadedFile("tabela.png", make_image(), content_type="image/png"), original_name="tabela.png", mime_type="image/png", size_bytes=100, sha256="no-confirm")
    with pytest.raises(RuntimeError, match="precisa de IA"):
        ExtractionService().process(document, paid_confirmed=False)
    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
