"""Política de tentativas, pré-condições da IA e acesso à página de processamento."""
import io

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle

from documentos.models import Document, ExtractionCache
from extracao.gemini_service import GeminiExtractionError
from extracao.services import (
    AIConfirmationRequired,
    AINotConfigured,
    AttemptsExhausted,
    BudgetExceeded,
    ExtractionService,
    ProcessingInProgress,
)


def make_image():
    from PIL import Image

    out = io.BytesIO()
    Image.new("RGB", (100, 50), "white").save(out, format="PNG")
    return out.getvalue()


def make_table_pdf():
    out = io.BytesIO()
    doc = SimpleDocTemplate(out, pagesize=A4)
    table = Table([["Código", "Valor"], ["0012", "R$ 10,50"]])
    table.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 1, colors.black)]))
    doc.build([table])
    return out.getvalue()


class SpyExtractor:
    """Extractor simulado: registra chamadas e nunca acessa a rede."""

    def __init__(self, configured=True, failure=None):
        self.configured = configured
        self.failure = failure
        self.calls = 0

    def is_configured(self):
        return self.configured

    def extract(self, **kwargs):
        self.calls += 1
        if self.failure:
            raise self.failure
        self.last_metrics = {"input_tokens": 10, "output_tokens": 5, "api_calls": 1}
        return {
            "document_name": "ficha.png",
            "pages": [{"page_number": 1, "tables": [{"headers": [{"value": "Código"}], "rows": [[{"value": "0012"}]], "merged_cells": [], "alerts": []}], "alerts": []}],
            "alerts": [],
        }, 15


def make_image_document(user, sha256, **kwargs):
    return Document.objects.create(
        user=user,
        file=SimpleUploadedFile("ficha.png", make_image(), content_type="image/png"),
        original_name="ficha.png",
        mime_type="image/png",
        size_bytes=100,
        sha256=sha256,
        **kwargs,
    )


# --- Pré-condições não consomem tentativa, nem chamam a API -------------------


@pytest.mark.django_db
def test_falta_de_chave_nao_consome_tentativa_nem_chama_api(user):
    document = make_image_document(user, "sem-chave")
    extractor = SpyExtractor(configured=False)
    with pytest.raises(AINotConfigured):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert extractor.calls == 0
    assert document.retry_count == 0
    assert document.status == Document.Status.FAILED
    assert document.can_retry


@pytest.mark.django_db
def test_falta_de_confirmacao_nao_consome_tentativa_nem_chama_api(user):
    document = make_image_document(user, "sem-confirmacao")
    extractor = SpyExtractor()
    with pytest.raises(AIConfirmationRequired):
        ExtractionService(extractor).process(document, paid_confirmed=False)
    document.refresh_from_db()
    assert extractor.calls == 0
    assert document.retry_count == 0
    assert document.can_retry


@pytest.mark.django_db
def test_repetir_sem_chave_nunca_esgota_tentativas(user):
    """A regressão original: sem chave, o documento travava após 3 envios."""
    document = make_image_document(user, "repete-sem-chave")
    extractor = SpyExtractor(configured=False)
    service = ExtractionService(extractor)
    for _ in range(5):
        with pytest.raises(AINotConfigured):
            service.process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert extractor.calls == 0
    assert document.retry_count == 0
    assert document.can_retry


@pytest.mark.django_db
def test_orcamento_excedido_nao_consome_tentativa(user, settings):
    settings.MAX_MONTHLY_API_CALLS = 0
    document = make_image_document(user, "sem-orcamento")
    extractor = SpyExtractor()
    with pytest.raises(BudgetExceeded):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert extractor.calls == 0
    assert document.retry_count == 0


@pytest.mark.django_db
def test_limite_atingido_nao_incrementa_mais_tentativas(user):
    document = make_image_document(user, "esgotado", retry_count=Document.MAX_ATTEMPTS)
    extractor = SpyExtractor()
    with pytest.raises(AttemptsExhausted):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert extractor.calls == 0
    assert document.retry_count == Document.MAX_ATTEMPTS


# --- Caminhos sem custo continuam funcionando sem chave ----------------------


@pytest.mark.django_db
def test_extracao_local_funciona_sem_chave(user):
    document = Document.objects.create(
        user=user,
        file=SimpleUploadedFile("tabela.pdf", make_table_pdf(), content_type="application/pdf"),
        original_name="tabela.pdf",
        mime_type="application/pdf",
        size_bytes=100,
        sha256="local-sem-chave",
    )
    extractor = SpyExtractor(configured=False)
    payload = ExtractionService(extractor).process(document, paid_confirmed=False)
    document.refresh_from_db()
    assert extractor.calls == 0
    assert document.status == Document.Status.READY
    assert document.retry_count == 0
    assert payload["pages"][0]["tables"][0]["rows"][0][0]["value"] == "0012"


@pytest.mark.django_db
def test_cache_funciona_sem_chave_e_sem_confirmacao(user):
    first = make_image_document(user, "cacheado")
    ExtractionService(SpyExtractor()).process(first, paid_confirmed=True)
    assert ExtractionCache.objects.filter(cache_key__isnull=False).exists()

    # Mesmo sha256: o cache atende sem chave e sem confirmação de custo.
    second = make_image_document(user, "cacheado")
    extractor = SpyExtractor(configured=False)
    ExtractionService(extractor).process(second, paid_confirmed=False)
    second.refresh_from_db()
    assert extractor.calls == 0
    assert second.status == Document.Status.READY
    assert second.retry_count == 0


# --- Falhas reais são contabilizadas ----------------------------------------


@pytest.mark.django_db
def test_falha_real_da_gemini_consome_tentativa(user):
    document = make_image_document(user, "falha-real")
    failure = GeminiExtractionError(
        "A Gemini respondeu em formato inválido.",
        error_code="invalid_json",
    )
    extractor = SpyExtractor(failure=failure)
    with pytest.raises(GeminiExtractionError):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert extractor.calls == 1
    assert document.retry_count == 1
    assert document.status == Document.Status.FAILED


@pytest.mark.django_db
def test_tres_falhas_reais_esgotam_as_tentativas(user):
    document = make_image_document(user, "falha-repetida")
    extractor = SpyExtractor(failure=GeminiExtractionError("erro", error_code="internal"))
    service = ExtractionService(extractor)
    for _ in range(Document.MAX_ATTEMPTS):
        with pytest.raises(GeminiExtractionError):
            service.process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.retry_count == Document.MAX_ATTEMPTS
    assert document.attempts_exhausted
    # A partir daqui o bloqueio é de pré-condição e não chama mais a API.
    with pytest.raises(AttemptsExhausted):
        service.process(document, paid_confirmed=True)
    assert extractor.calls == Document.MAX_ATTEMPTS


@pytest.mark.django_db
def test_chave_recusada_pelo_provedor_consome_tentativa(user):
    """Credencial presente mas rejeitada é tentativa real, diferente de ausência."""
    document = make_image_document(user, "chave-recusada")
    failure = GeminiExtractionError(
        "A credencial da Gemini foi recusada.",
        error_code="UNAUTHENTICATED",
        http_status=401,
    )
    extractor = SpyExtractor(failure=failure)
    with pytest.raises(GeminiExtractionError):
        ExtractionService(extractor).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert document.retry_count == 1


# --- Submissões duplicadas ---------------------------------------------------


@pytest.mark.django_db
def test_submissao_duplicada_nao_inicia_segunda_chamada(user):
    document = make_image_document(user, "duplicado")
    extractor = SpyExtractor()
    service = ExtractionService(extractor)

    # Simula a primeira submissão já em andamento.
    Document.objects.filter(pk=document.pk).update(status=Document.Status.PROCESSING)
    concurrent = Document.objects.get(pk=document.pk)
    with pytest.raises(ProcessingInProgress):
        service.process(concurrent, paid_confirmed=True)
    concurrent.refresh_from_db()
    assert extractor.calls == 0
    assert concurrent.retry_count == 0
    assert concurrent.status == Document.Status.PROCESSING


@pytest.mark.django_db
def test_post_duplicado_na_view_nao_dispara_segunda_extracao(client, user):
    document = make_image_document(user, "duplicado-view")
    Document.objects.filter(pk=document.pk).update(status=Document.Status.PROCESSING)
    client.force_login(user)
    response = client.post(reverse("processamento", args=[document.pk]), {"confirm_paid": "on"})
    assert response.status_code == 200
    assert "já está sendo processado" in response.content.decode()
    document.refresh_from_db()
    assert document.retry_count == 0


# --- Acesso e isolamento -----------------------------------------------------


@pytest.mark.django_db
def test_proprietario_acessa_documento_com_falha(client, user):
    document = make_image_document(user, "falhou", status=Document.Status.FAILED, retry_count=1, error_message="Falha anterior")
    client.force_login(user)
    response = client.get(reverse("processamento", args=[document.pk]))
    assert response.status_code == 200
    assert "Falha anterior" in response.content.decode()


@pytest.mark.django_db
def test_documento_com_tentativas_esgotadas_segue_acessivel_e_bloqueado(client, user):
    document = make_image_document(user, "esgotado-view", status=Document.Status.FAILED, retry_count=Document.MAX_ATTEMPTS)
    client.force_login(user)
    response = client.get(reverse("processamento", args=[document.pk]))
    body = response.content.decode()
    assert response.status_code == 200
    assert "Tentativas esgotadas" in body
    assert "reset_document_attempts" in body


@pytest.mark.django_db
def test_outro_usuario_nao_acessa_documento(client, user, other_user):
    document = make_image_document(user, "privado", status=Document.Status.FAILED)
    client.force_login(other_user)
    response = client.get(reverse("processamento", args=[document.pk]))
    assert response.status_code == 404
    body = response.content.decode()
    assert "ficha.png" not in body
    assert "Não encontramos este documento" in body


@pytest.mark.django_db
def test_outro_usuario_nao_processa_documento(client, user, other_user):
    document = make_image_document(user, "privado-post")
    client.force_login(other_user)
    response = client.post(reverse("processamento", args=[document.pk]), {"confirm_paid": "on"})
    assert response.status_code == 404
    document.refresh_from_db()
    assert document.status == Document.Status.UPLOADED
    assert document.retry_count == 0


@pytest.mark.django_db
def test_uuid_inexistente_recebe_pagina_amigavel(client, user):
    client.force_login(user)
    response = client.get(reverse("processamento", args=["ffffffff-ffff-4fff-8fff-ffffffffffff"]))
    assert response.status_code == 404
    body = response.content.decode()
    assert "Não encontramos este documento" in body
    assert reverse("historico") in body
    assert reverse("documentos:upload") in body


@pytest.mark.django_db
def test_pagina_amigavel_independe_de_debug(client, user, settings):
    """A correção não depende de DEBUG=False: a página é renderizada nos dois modos."""
    client.force_login(user)
    for debug in (True, False):
        settings.DEBUG = debug
        response = client.get(reverse("processamento", args=["ffffffff-ffff-4fff-8fff-ffffffffffff"]))
        assert response.status_code == 404
        body = response.content.decode()
        assert "Não encontramos este documento" in body
        assert "No Document matches the given query" not in body


# --- Comando administrativo --------------------------------------------------


@pytest.mark.django_db
def test_comando_redefine_tentativas_do_documento(user):
    document = make_image_document(user, "reset", status=Document.Status.FAILED, retry_count=8, error_message="falha antiga")
    other = make_image_document(user, "intacto", status=Document.Status.FAILED, retry_count=2)
    call_command("reset_document_attempts", str(document.pk))
    document.refresh_from_db()
    other.refresh_from_db()
    assert document.retry_count == 0
    assert document.status == Document.Status.UPLOADED
    assert document.error_message == ""
    assert document.can_retry
    # Nenhum outro registro é alterado.
    assert other.retry_count == 2
    assert other.status == Document.Status.FAILED


@pytest.mark.django_db
def test_comando_informa_uuid_inexistente(user):
    document = make_image_document(user, "nao-alterado", retry_count=2)
    with pytest.raises(CommandError, match="não encontrado"):
        call_command("reset_document_attempts", "ffffffff-ffff-4fff-8fff-ffffffffffff")
    document.refresh_from_db()
    assert document.retry_count == 2


@pytest.mark.django_db
def test_comando_rejeita_uuid_malformado():
    with pytest.raises(CommandError, match="não é um UUID válido"):
        call_command("reset_document_attempts", "nao-e-uuid")


@pytest.mark.django_db
def test_comando_recusa_documento_em_processamento(user):
    document = make_image_document(user, "em-andamento", status=Document.Status.PROCESSING, retry_count=2)
    with pytest.raises(CommandError, match="em processamento"):
        call_command("reset_document_attempts", str(document.pk))
    document.refresh_from_db()
    assert document.retry_count == 2


@pytest.mark.django_db
def test_documento_redefinido_volta_a_processar(user):
    document = make_image_document(user, "reset-processa", status=Document.Status.FAILED, retry_count=Document.MAX_ATTEMPTS)
    extractor = SpyExtractor()
    with pytest.raises(AttemptsExhausted):
        ExtractionService(extractor).process(document, paid_confirmed=True)

    call_command("reset_document_attempts", str(document.pk))
    document.refresh_from_db()
    ExtractionService(extractor).process(document, paid_confirmed=True)
    document.refresh_from_db()
    assert extractor.calls == 1
    assert document.status == Document.Status.READY
