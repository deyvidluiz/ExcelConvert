import io
import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import load_workbook
from PIL import Image, ImageDraw

from documentos.models import Document
from extracao.services import ExtractionService
from modelos.services import register_cemig_template


def handwritten_like_image():
    output = io.BytesIO()
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 1140, 1540), outline="black", width=4)
    draw.line((120, 240, 1000, 240), fill="black", width=3)
    draw.text((140, 180), "FICHA DE ENSAIO", fill="black")
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.django_db
def test_fluxo_integrado_mockado_login_upload_editor_excel_historico(client, user, monkeypatch):
    template = register_cemig_template()
    client.force_login(user)

    response = client.post(
        reverse("documentos:upload"),
        {
            "files": SimpleUploadedFile("ficha-cemig.png", handwritten_like_image(), content_type="image/png"),
            "template": str(template.pk),
        },
    )
    assert response.status_code == 302
    document = Document.objects.get(user=user)
    assert document.template_id == template.pk
    Document.objects.filter(pk=document.pk).update(error_message="mensagem residual")

    class FakeExtractor:
        calls = 0
        last_metrics = {"input_tokens": 210, "output_tokens": 55, "total_tokens": 265, "api_calls": 1}

        def extract(self, **kwargs):
            self.calls += 1
            assert kwargs["template"].code == template.code
            return (
                {
                    "document_name": "ficha-cemig.png",
                    "template_code": template.code,
                    "template_version": template.version,
                    "template_fields": [
                        {
                            "field_id": "numero_serie",
                            "name": "Número de série",
                            "section": "Identificação da instalação e do equipamento",
                            "page_number": 1,
                            "value": "0007",
                            "ambiguous": False,
                            "review_reason": None,
                        }
                    ],
                    "pages": [
                        {
                            "page_number": 1,
                            "tables": [
                                {
                                    "title": "Identificação",
                                    "headers": [{"value": "Campo"}, {"value": "Valor"}],
                                    "rows": [[{"value": "Número de série"}, {"value": "0007", "field_id": "numero_serie"}]],
                                    "merged_cells": [],
                                    "alerts": [],
                                }
                            ],
                            "alerts": [],
                        }
                    ],
                    "alerts": [],
                },
                265,
            )

    fake = FakeExtractor()
    monkeypatch.setattr("documentos.views.ExtractionService", lambda: ExtractionService(fake))

    response = client.post(reverse("processamento", args=[document.pk]), {"confirm_paid": "on"})
    assert response.status_code == 302
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert fake.calls == 1
    assert document.input_token_count == 210
    assert document.output_token_count == 55
    assert document.error_message == ""

    response = client.get(reverse("validacao:editor", args=[document.pk]))
    assert response.status_code == 200
    assert "0007" in response.content.decode()

    payload = document.extraction_payload
    payload["pages"][0]["tables"][0]["rows"][0][1]["value"] = "0009"
    response = client.post(
        reverse("validacao:editor", args=[document.pk]),
        {"payload": json.dumps(payload, ensure_ascii=False)},
    )
    assert response.status_code == 200
    document.refresh_from_db()
    assert document.extraction_payload["pages"][0]["tables"][0]["rows"][0][1]["value"] == "0009"

    response = client.get(reverse("exportacao:download", args=[document.pk, "xlsx"]))
    assert response.status_code == 200
    workbook = load_workbook(io.BytesIO(response.content))
    assert workbook["P1 T1"]["B4"].value == "0009"

    response = client.get(reverse("historico"))
    assert response.status_code == 200
    assert "ficha-cemig.png" in response.content.decode()


@pytest.mark.django_db
def test_retencao_exclui_documento_e_arquivos(client, user, settings):
    settings.DOCUMENT_RETENTION_DAYS = 1
    document = Document.objects.create(
        user=user,
        file=SimpleUploadedFile("privado.png", handwritten_like_image(), content_type="image/png"),
        original_name="privado.png",
        mime_type="image/png",
        size_bytes=10,
        sha256="retention",
    )
    Document.objects.filter(pk=document.pk).update(created_at="2020-01-01T00:00:00Z")
    from django.core.management import call_command as run_command

    run_command("purge_documents", days=1)
    assert not Document.objects.filter(pk=document.pk).exists()
