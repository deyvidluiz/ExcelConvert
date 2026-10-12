import io

import fitz
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from documentos.models import Document


@pytest.mark.django_db
def test_usuario_nao_acessa_documento_de_outro_usuario(client, user, other_user):
    pdf = fitz.open()
    pdf.new_page()
    document = Document.objects.create(user=other_user, file=SimpleUploadedFile("privado.pdf", pdf.tobytes(), content_type="application/pdf"), original_name="privado.pdf", mime_type="application/pdf", size_bytes=100, sha256="private")
    client.force_login(user)
    assert client.get(reverse("documentos:file", args=[document.pk])).status_code == 404
    assert client.get(reverse("validacao:editor", args=[document.pk])).status_code == 404
