import io
import logging
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image, ImageDraw

from documentos.models import Document
from extracao.gemini_service import GeminiExtractionError, GeminiExtractor, _classify_exception, check_model_availability
from extracao.services import ExtractionService
from extracao.schemas import TemplateExtraction, TemplateFieldValue


class ProviderFailure(Exception):
    def __init__(self, code=None, status=None, message="provider failure"):
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message


@pytest.mark.parametrize(
    ("failure", "expected_code", "expected_status"),
    [
        (ProviderFailure(401, "UNAUTHENTICATED", "bad credential"), "UNAUTHENTICATED", 401),
        (ProviderFailure(403, "PERMISSION_DENIED", "forbidden"), "PERMISSION_DENIED", 403),
        (ProviderFailure(404, "NOT_FOUND", "model missing"), "NOT_FOUND", 404),
        (ProviderFailure(429, "RESOURCE_EXHAUSTED", "quota"), "RESOURCE_EXHAUSTED", 429),
        (TimeoutError("request timed out"), "timeout", None),
        (ConnectionError("connection refused"), "connection_error", None),
    ],
)
def test_classifica_falhas_gemini(failure, expected_code, expected_status):
    error = _classify_exception(failure, model="gemini-3.1-flash-lite", operation="generate_content")
    assert isinstance(error, GeminiExtractionError)
    assert error.error_code == expected_code
    assert error.http_status == expected_status
    assert error.user_message


def test_log_sanitiza_chave_e_nao_registra_dados_do_documento(caplog):
    failure = ProviderFailure(
        401,
        "UNAUTHENTICATED",
        "authorization: Bearer AQ.TEST_SECRET_VALUE_123456789 document: ficha-cliente-joao.png",
    )
    with caplog.at_level(logging.ERROR, logger="extracao.gemini_service"):
        _classify_exception(failure, model="gemini-3.1-flash-lite", operation="generate_content")
    assert "401" in caplog.text
    assert "UNAUTHENTICATED" in caplog.text
    assert "gemini-3.1-flash-lite" in caplog.text
    assert "AQ.TEST_SECRET_VALUE_123456789" not in caplog.text
    assert "ficha-cliente-joao.png" not in caplog.text
    assert "authorization: Bearer" not in caplog.text


def test_resposta_json_invalida_tem_mensagem_segura(caplog):
    extractor = GeminiExtractor(model="gemini-3.1-flash-lite")
    with pytest.raises(GeminiExtractionError) as raised:
        extractor._parse(SimpleNamespace(parsed=None, text="{invalid"), TemplateExtraction)
    assert raised.value.error_code == "invalid_json"
    assert "formato inválido" in raised.value.user_message
    assert "invalid" not in raised.value.user_message
    assert "invalid_json" in caplog.text


def test_sdk_recebe_modelo_e_configuracao_de_json(monkeypatch):
    response = SimpleNamespace(
        parsed=TemplateExtraction(
            template_code="teste",
            template_version="1.0.0",
            fields=[TemplateFieldValue(field_id="valor", page_number=1, value="0008")],
        ),
        usage_metadata=SimpleNamespace(prompt_token_count=10, candidates_token_count=5, total_token_count=15),
    )
    monkeypatch.setenv("GEMINI_API_KEY", "mocked-key")
    with patch("google.genai.Client") as client_class:
        client_class.return_value.models.generate_content.return_value = response
        extractor = GeminiExtractor(model="gemini-3.1-flash-lite")
        template = SimpleNamespace(code="teste", version="1.0.0", repeat_layout_per_page=False, schema_for_prompt=[])
        template.fields = SimpleNamespace(all=lambda: [])
        payload, tokens = extractor.extract_template(
            data=b"image",
            mime_type="image/png",
            document_name="ficha.png",
            template=template,
        )
    assert payload["template_fields"][0]["value"] == "0008"
    assert tokens == 15
    call = client_class.return_value.models.generate_content.call_args
    assert call.kwargs["model"] == "gemini-3.1-flash-lite"
    assert call.kwargs["config"].response_mime_type == "application/json"
    assert call.kwargs["config"].temperature == 0


def test_check_metadata_exige_suporte_a_generate_content(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mocked-key")
    info = SimpleNamespace(
        name="models/gemini-3.1-flash-lite",
        display_name="Gemini Flash-Lite",
        supported_actions=["generateContent"],
        input_token_limit=1000,
        output_token_limit=100,
    )
    with patch("google.genai.Client") as client_class:
        client_class.return_value.models.get.return_value = info
        result = check_model_availability(model="gemini-3.1-flash-lite")
    assert result["generation_supported"] is True
    assert result["supported_actions"] == ["generateContent"]


def test_check_metadata_rejeita_modelo_sem_generate_content(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "mocked-key")
    info = SimpleNamespace(supported_actions=["countTokens"])
    with patch("google.genai.Client") as client_class:
        client_class.return_value.models.get.return_value = info
        with pytest.raises(GeminiExtractionError) as raised:
            check_model_availability(model="gemini-3.1-flash-lite")
    assert raised.value.error_code == "generation_not_supported"


def handwritten_image():
    output = io.BytesIO()
    image = Image.new("RGB", (1200, 1600), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 60, 1140, 1540), outline="black", width=4)
    image.save(output, format="PNG")
    return output.getvalue()


@pytest.mark.django_db
def test_view_exibe_mensagem_segura_para_erro_de_autenticacao(client, user, monkeypatch):
    document = Document.objects.create(
        user=user,
        file=SimpleUploadedFile("ficha.png", handwritten_image(), content_type="image/png"),
        original_name="ficha.png",
        mime_type="image/png",
        size_bytes=100,
        sha256="auth-error",
    )

    class FailingExtractor:
        last_metrics = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "api_calls": 0}

        def extract(self, **kwargs):
            raise GeminiExtractionError(
                "A credencial da Gemini foi recusada. Verifique a GEMINI_API_KEY configurada.",
                error_code="UNAUTHENTICATED",
                http_status=401,
            )

    client.force_login(user)
    monkeypatch.setattr("documentos.views.ExtractionService", lambda: ExtractionService(FailingExtractor()))
    response = client.post(reverse("processamento", args=[document.pk]), {"confirm_paid": "on"})
    assert response.status_code == 200
    assert "credencial da Gemini foi recusada" in response.content.decode()
    assert "UNAUTHENTICATED" not in response.content.decode()
    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert document.error_message == "A credencial da Gemini foi recusada. Verifique a GEMINI_API_KEY configurada."
