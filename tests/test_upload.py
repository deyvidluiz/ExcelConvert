import io

import fitz
import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from documentos.models import Document
from documentos.services import inspect_upload


def pdf_bytes():
    pdf = fitz.open()
    pdf.new_page()
    data = pdf.tobytes()
    pdf.close()
    return data


@pytest.mark.django_db
def test_upload_pdf_valido(client, user, settings):
    client.force_login(user)
    response = client.post(reverse("documentos:upload"), {"files": SimpleUploadedFile("tabela.pdf", pdf_bytes(), content_type="application/pdf")})
    assert response.status_code == 302
    document = Document.objects.get()
    assert document.mime_type == "application/pdf"
    assert document.page_count == 1


@pytest.mark.django_db
def test_upload_imagem_valida(client, user):
    image = Image.new("RGB", (80, 40), "white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    client.force_login(user)
    response = client.post(reverse("documentos:upload"), {"files": SimpleUploadedFile("tabela.png", buffer.getvalue(), content_type="image/png")})
    assert response.status_code == 302
    assert Document.objects.get().mime_type == "image/png"


@pytest.mark.django_db
def test_upload_rejeita_arquivo_invalido(client, user):
    client.force_login(user)
    response = client.post(reverse("documentos:upload"), {"files": SimpleUploadedFile("dados.txt", b"nao e tabela", content_type="text/plain")})
    assert response.status_code == 200
    assert not Document.objects.exists()
    assert "formato não suportado" in response.content.decode()


def test_inspect_upload_rejeita_pdf_falso():
    upload = SimpleUploadedFile("falso.pdf", b"%PDF-nao-valido", content_type="application/pdf")
    with pytest.raises(Exception):
        inspect_upload(upload)
