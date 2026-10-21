"""Indisponibilidade temporária do provedor (503/UNAVAILABLE).

Todas as respostas são simuladas: nenhuma chamada paga é feita.
"""
import io
import logging

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from documentos.models import Document
from extracao.gemini_service import (
    PROVIDER_BUSY_MESSAGE,
    GeminiExtractionError,
    GeminiExtractor,
    _classify_exception,
)
from extracao.services import ExtractionService, consumes_attempt
from modelos.models import DocumentTemplate


class ProviderUnavailable(Exception):
    """Reproduz a exceção do SDK para 503 UNAVAILABLE."""

    def __init__(self, message="This model is currently experiencing high demand."):
        super().__init__(message)
        self.code = 503
        self.status = "UNAVAILABLE"
        self.message = message


def make_image():
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(out, format="PNG")
    return out.getvalue()


class BusyExtractor:
    """Extractor simulado que devolve 503 e registra a tentativa de chamada."""

    def __init__(self):
        self.calls = 0
        self.last_metrics = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "api_calls": 0, "usage_reported": False}

    def is_configured(self):
        return True

    def extract(self, **kwargs):
        self.calls += 1
        # Igual ao extractor real: a tentativa é registrada antes do envio.
        self.last_metrics = {**self.last_metrics, "api_calls": 1, "usage_reported": False}
        raise _classify_exception(ProviderUnavailable(), model="gemini-3.1-flash-lite", operation="generate_content")


def make_document(user, sha256, **kwargs):
    return Document.objects.create(
        user=user,
        file=SimpleUploadedFile("ficha.png", make_image(), content_type="image/png"),
        original_name="ficha.png",
        mime_type="image/png",
        size_bytes=100,
        sha256=sha256,
        **kwargs,
    )


# --- Classificação -----------------------------------------------------------


def test_503_e_classificado_como_indisponibilidade_temporaria():
    error = _classify_exception(ProviderUnavailable(), model="gemini-3.1-flash-lite", operation="generate_content")
    assert isinstance(error, GeminiExtractionError)
    assert error.http_status == 503
    assert error.error_code == "UNAVAILABLE"
    assert error.transient is True
    assert error.user_message == "O serviço de IA está temporariamente ocupado. Aguarde um pouco e tente novamente."


def test_indisponibilidade_nao_consome_tentativa_por_politica():
    error = _classify_exception(ProviderUnavailable(), model="gemini-3.1-flash-lite", operation="generate_content")
    assert consumes_attempt(error) is False


@pytest.mark.parametrize("status_code", [502, 503])
def test_sobrecarga_em_varios_status_e_transitoria(status_code):
    failure = ProviderUnavailable()
    failure.code = status_code
    error = _classify_exception(failure, model="gemini-3.1-flash-lite", operation="generate_content")
    assert error.transient is True
    assert error.user_message == PROVIDER_BUSY_MESSAGE


def test_erro_generico_do_provedor_continua_consumindo_tentativa():
    """A mudança não afrouxa a política para falhas atribuíveis à requisição."""
    failure = ProviderUnavailable()
    failure.code = 400
    failure.status = "INVALID_ARGUMENT"
    error = _classify_exception(failure, model="gemini-3.1-flash-lite", operation="generate_content")
    assert error.transient is False
    assert consumes_attempt(error) is True


def test_log_do_503_tem_status_codigo_e_modelo_sem_credencial(caplog):
    failure = ProviderUnavailable(
        "high demand; x-goog-api-key: AQ.TEST_SECRET_VALUE_123456 for document ficha-cliente.png"
    )
    with caplog.at_level(logging.ERROR, logger="extracao.gemini_service"):
        _classify_exception(failure, model="gemini-3.1-flash-lite", operation="generate_content")
    assert "503" in caplog.text
    assert "UNAVAILABLE" in caplog.text
    assert "gemini-3.1-flash-lite" in caplog.text
    assert "AQ.TEST_SECRET_VALUE_123456" not in caplog.text
    assert "ficha-cliente.png" not in caplog.text


# --- Efeito no documento -----------------------------------------------------


@pytest.mark.django_db
def test_503_nao_consome_tentativa_e_preserva_documento(user):
    document = make_document(user, "ocupado")
    extractor = BusyExtractor()
    with pytest.raises(GeminiExtractionError) as excinfo:
        ExtractionService(extractor).process(document, paid_confirmed=True)
    assert excinfo.value.transient is True

    document.refresh_from_db()
    assert document.retry_count == 0
    assert document.can_retry
    assert document.status == Document.Status.FAILED
    assert document.error_message == PROVIDER_BUSY_MESSAGE
    # Arquivo preservado e legível.
    assert document.file.name
    with document.file.open("rb") as handle:
        assert handle.read(8) == b"\x89PNG\r\n\x1a\n"


@pytest.mark.django_db
def test_503_preserva_o_modelo_selecionado(user):
    template = DocumentTemplate.objects.create(code="TCA-TESTE", name="TCA Teste", version="1.0.0")
    document = make_document(user, "ocupado-modelo", template=template)
    with pytest.raises(GeminiExtractionError):
        ExtractionService(BusyExtractor()).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.template_id == template.pk
    assert document.template.name == "TCA Teste"


@pytest.mark.django_db
def test_503_registra_tentativa_e_falha_separadamente(user):
    document = make_document(user, "contabiliza")
    extractor = BusyExtractor()
    with pytest.raises(GeminiExtractionError):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert extractor.calls == 1
    assert document.api_attempt_count == 1
    assert document.provider_failure_count == 1
    # A tentativa do provedor não vira tentativa do documento.
    assert document.retry_count == 0
    # api_call_count segue contando apenas chamadas que produziram resultado.
    assert document.api_call_count == 0


@pytest.mark.django_db
def test_503_repetido_nunca_esgota_as_tentativas(user):
    document = make_document(user, "ocupado-repetido")
    extractor = BusyExtractor()
    service = ExtractionService(extractor)
    for _ in range(Document.MAX_ATTEMPTS + 3):
        with pytest.raises(GeminiExtractionError):
            service.process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.retry_count == 0
    assert document.can_retry
    assert document.api_attempt_count == Document.MAX_ATTEMPTS + 3
    assert document.provider_failure_count == Document.MAX_ATTEMPTS + 3


@pytest.mark.django_db
def test_503_nao_registra_custo_zero_como_certeza(user):
    document = make_document(user, "sem-custo")
    with pytest.raises(GeminiExtractionError):
        ExtractionService(BusyExtractor()).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.usage_reported is False
    assert document.cost_is_known is False


@pytest.mark.django_db
def test_sucesso_sem_usage_do_provedor_nao_afirma_custo(user):
    """Resposta válida sem usage_metadata: custo fica marcado como desconhecido."""

    class NoUsageExtractor:
        def is_configured(self):
            return True

        def extract(self, **kwargs):
            self.last_metrics = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "api_calls": 1, "usage_reported": False}
            return {
                "document_name": "ficha.png",
                "pages": [{"page_number": 1, "tables": [{"headers": [{"value": "C"}], "rows": [[{"value": "1"}]], "merged_cells": [], "alerts": []}], "alerts": []}],
                "alerts": [],
            }, 0

    document = make_document(user, "sem-usage")
    ExtractionService(NoUsageExtractor()).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert document.usage_reported is False
    assert document.cost_is_known is False


@pytest.mark.django_db
def test_extracao_local_mantem_custo_zero_confiavel(user):
    """Zero local é certeza, diferente de consumo não informado."""
    from tests.test_processing_flow import make_table_pdf

    document = Document.objects.create(
        user=user,
        file=SimpleUploadedFile("tabela.pdf", make_table_pdf(), content_type="application/pdf"),
        original_name="tabela.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        sha256="local-custo",
    )
    ExtractionService(BusyExtractor()).process(document, paid_confirmed=False)
    document.refresh_from_db()
    assert document.status == Document.Status.READY
    assert document.cost_is_known is True


# --- Estado de processamento e concorrência ----------------------------------


@pytest.mark.django_db
def test_503_encerra_o_estado_de_processamento(user):
    document = make_document(user, "encerra-estado")
    with pytest.raises(GeminiExtractionError):
        ExtractionService(BusyExtractor()).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.status == Document.Status.FAILED
    assert not document.is_processing
    # Estado encerrado significa que uma nova tentativa é aceita.
    extractor = BusyExtractor()
    with pytest.raises(GeminiExtractionError):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    assert extractor.calls == 1


@pytest.mark.django_db
def test_nova_chamada_exige_acao_do_usuario(user):
    """Uma submissão gera exatamente uma chamada: sem repetição automática."""
    document = make_document(user, "sem-auto-retry")
    extractor = BusyExtractor()
    with pytest.raises(GeminiExtractionError):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    assert extractor.calls == 1


@pytest.mark.django_db
def test_nao_troca_de_modelo_silenciosamente(user, settings):
    document = make_document(user, "mesmo-modelo")
    usados = []

    class ModelSpy(BusyExtractor):
        def extract(self, **kwargs):
            usados.append(settings.GEMINI_MODEL)
            return super().extract(**kwargs)

    service = ExtractionService(ModelSpy())
    for _ in range(2):
        with pytest.raises(GeminiExtractionError):
            service.process(document, paid_confirmed=True)
    assert usados == [settings.GEMINI_MODEL, settings.GEMINI_MODEL]


@pytest.mark.django_db
def test_503_nao_permite_chamada_simultanea(user):
    document = make_document(user, "concorrente")
    Document.objects.filter(pk=document.pk).update(status=Document.Status.PROCESSING)
    concurrent = Document.objects.get(pk=document.pk)
    extractor = BusyExtractor()
    from extracao.services import ProcessingInProgress

    with pytest.raises(ProcessingInProgress):
        ExtractionService(extractor).process(concurrent, paid_confirmed=True)
    assert extractor.calls == 0


# --- Interface ---------------------------------------------------------------


@pytest.mark.django_db
def test_mensagem_do_503_aparece_na_interface(client, user, monkeypatch):
    document = make_document(user, "interface")
    monkeypatch.setattr(
        "documentos.views.ExtractionService",
        lambda *args, **kwargs: ExtractionService(BusyExtractor()),
    )
    client.force_login(user)
    response = client.post(
        reverse("processamento", args=[document.pk]), {"confirm_paid": "on"}, follow=True
    )
    body = response.content.decode()
    assert response.status_code == 200
    assert "O serviço de IA está temporariamente ocupado. Aguarde um pouco e tente novamente." in body
    assert "Serviço de IA ocupado" in body
    assert "não consumiu nenhuma tentativa" in body
    # Documento segue disponível para nova tentativa pelo próprio usuário.
    assert "Tentativas esgotadas" not in body
    document.refresh_from_db()
    assert document.can_retry
    assert document.retry_count == 0


@pytest.mark.django_db
def test_pagina_mostra_estado_ocupado_em_visita_posterior(client, user):
    document = make_document(
        user,
        "interface-get",
        status=Document.Status.FAILED,
        error_message=PROVIDER_BUSY_MESSAGE,
    )
    client.force_login(user)
    body = client.get(reverse("processamento", args=[document.pk])).content.decode()
    assert "Serviço de IA ocupado" in body
    assert PROVIDER_BUSY_MESSAGE in body


@pytest.mark.django_db
def test_historico_nao_exibe_custo_zero_como_certeza(client, user):
    make_document(user, "hist-desconhecido", status=Document.Status.READY, usage_reported=False, model="gemini-3.1-flash-lite")
    client.force_login(user)
    body = client.get(reverse("historico")).content.decode()
    assert "não informado" in body


# --- Extractor real ----------------------------------------------------------


def test_extractor_real_registra_tentativa_antes_do_envio(monkeypatch):
    """A tentativa precisa existir mesmo quando o provedor devolve 503.

    O SDK é substituído por stubs: nenhuma requisição sai da máquina.
    """
    monkeypatch.setenv("GEMINI_API_KEY", "chave-simulada-para-teste")
    extractor = GeminiExtractor(model="gemini-3.1-flash-lite")

    class FakeModels:
        def generate_content(self, **kwargs):
            raise ProviderUnavailable()

    class FakeClient:
        def __init__(self, api_key=None):
            self.models = FakeModels()

    # Substitui apenas o Client no módulo real: "from google import genai" lê o
    # atributo do pacote já importado, então trocar sys.modules não bastaria.
    from google import genai

    monkeypatch.setattr(genai, "Client", FakeClient)

    with pytest.raises(GeminiExtractionError) as excinfo:
        extractor._generate(data=b"x", mime_type="image/png", prompt="p", schema=None)
    assert excinfo.value.transient is True
    assert excinfo.value.http_status == 503
    # A chamada foi registrada mesmo tendo falhado.
    assert extractor.last_metrics["api_calls"] == 1
    assert extractor.last_metrics["usage_reported"] is False
