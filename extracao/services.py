import hashlib
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone

from documentos.models import Document, ExtractionCache
from validacao.services import validate_payload

from .gemini_service import GeminiExtractionError, GeminiExtractor, gemini_is_configured
from .local_pdf import extract_pdf_tables
from .preprocessamento import crop_region, preprocess_image
from .prompts import PROMPT_VERSION
from .schemas import LAYOUT_CACHE_VERSION, normalise_layout_payload


#: Tempo após o qual um processamento travado em PROCESSING pode ser reivindicado.
PROCESSING_STALE_AFTER = timedelta(minutes=15)


class DocumentQualityError(RuntimeError):
    """Documento com qualidade insuficiente para extração."""

    #: A qualidade só é medida depois de pré-processar o arquivo: é tentativa real.
    consumes_attempt = True


class CacheNotFoundError(KeyError):
    """Cache de extração não encontrado."""
    pass


class ExtractionServiceError(RuntimeError):
    """Erro genérico de extração com código de erro."""

    #: Falhas genéricas ocorrem durante a extração, portanto consomem tentativa.
    consumes_attempt = True

    def __init__(self, message, error_code="extraction_error"):
        super().__init__(message)
        self.error_code = error_code


class PreflightError(ExtractionServiceError):
    """Bloqueio detectado antes de qualquer trabalho de extração.

    Nenhuma chamada à IA é feita e nenhum arquivo é processado, por isso estas
    falhas nunca consomem tentativa: o documento continua disponível para nova
    tentativa depois que a configuração for corrigida.
    """

    consumes_attempt = False


class AIConfirmationRequired(PreflightError):
    """Falta a confirmação explícita de custo para usar a IA."""

    def __init__(self, message="Este documento precisa de IA para ser processado. Marque a confirmação de custo e tente novamente.", error_code="confirmation_required"):
        super().__init__(message, error_code)


class AINotConfigured(PreflightError):
    """A credencial da Gemini não está configurada neste ambiente."""

    def __init__(self, message="A extração com IA não está configurada neste ambiente. Solicite ao administrador a configuração da Gemini.", error_code="missing_api_key"):
        super().__init__(message, error_code)


class BudgetExceeded(PreflightError):
    """Orçamento mensal estimado ou de chamadas já atingido."""

    def __init__(self, message, error_code="budget_exceeded"):
        super().__init__(message, error_code)


class AttemptsExhausted(PreflightError):
    """O documento já consumiu todas as tentativas reais permitidas."""

    def __init__(self, message=None, error_code="attempts_exhausted"):
        super().__init__(
            message or f"Limite de {Document.MAX_ATTEMPTS} tentativas atingido. Revise o arquivo ou solicite a redefinição das tentativas.",
            error_code,
        )


class ProcessingInProgress(PreflightError):
    """Já existe um processamento em andamento para este documento."""

    def __init__(self, message="Este documento já está sendo processado. Aguarde a conclusão antes de enviar novamente.", error_code="already_processing"):
        super().__init__(message, error_code)


def consumes_attempt(exc):
    """Decide se uma exceção representa uma tentativa real de processamento.

    Não consomem tentativa: falta de chave, falta de confirmação, orçamento
    excedido, limite já atingido e submissão duplicada — nenhuma delas chega a
    processar o arquivo. Também não consome a indisponibilidade momentânea do
    provedor (503/UNAVAILABLE): o documento está íntegro e o problema é externo.
    Consomem tentativa as falhas atribuíveis a esta requisição: credencial
    recusada, resposta inválida, qualidade insuficiente, falha de leitura local
    e erros internos durante a montagem do payload.
    """
    if isinstance(exc, GeminiExtractionError):
        if exc.error_code == "missing_api_key" or exc.transient:
            return False
        return True
    return getattr(exc, "consumes_attempt", True)


class ExtractionService:
    def __init__(self, gemini_extractor=None):
        self.gemini_extractor = gemini_extractor or GeminiExtractor()

    def process(self, document: Document, *, paid_confirmed=False):
        self._claim(document)
        try:
            payload, token_count, source, metrics = self._extract(document, paid_confirmed=paid_confirmed)
            payload = normalise_layout_payload(payload)
            payload["alerts"] = list(dict.fromkeys(payload.get("alerts", []) + validate_payload(payload)))
            document.extraction_payload = payload
            document.model = settings.GEMINI_MODEL if source == "gemini" else "local"
            document.token_count = token_count
            document.input_token_count = metrics.get("input_tokens", 0)
            document.output_token_count = metrics.get("output_tokens", 0)
            document.api_call_count = metrics.get("api_calls", 0)
            document.api_attempt_count += metrics.get("api_calls", 0)
            # Extração local tem consumo zero conhecido; na Gemini, depende do
            # que o provedor informou.
            document.usage_reported = True if source == "local" else bool(metrics.get("usage_reported", False))
            document.pages_processed = document.page_count
            document.estimated_cost_usd = self.estimate_cost(token_count) if source == "gemini" else Decimal("0")
            document.estimated_cost_brl = document.estimated_cost_usd * Decimal(str(settings.USD_TO_BRL))
            document.status = Document.Status.READY
            document.processed_at = timezone.now()
            document.save(update_fields=["model", "token_count", "input_token_count", "output_token_count", "api_call_count", "api_attempt_count", "usage_reported", "pages_processed", "estimated_cost_usd", "estimated_cost_brl", "extraction_payload", "error_message", "status", "processed_at", "updated_at"])
            return payload
        except ProcessingInProgress:
            # Não houve claim: o estado pertence à execução em andamento e não
            # deve ser encerrado aqui.
            raise
        except Exception as exc:
            # O claim foi adquirido, então o estado de processamento é encerrado
            # aqui em qualquer caminho de falha.
            document.status = Document.Status.FAILED
            document.error_message = self._failure_message(exc)
            update_fields = ["status", "error_message", "updated_at"]
            update_fields += self._record_provider_attempt(document, exc)
            if consumes_attempt(exc):
                document.retry_count += 1
                update_fields.append("retry_count")
            document.save(update_fields=update_fields)
            raise

    def _record_provider_attempt(self, document, exc):
        """Contabiliza chamada e falha do provedor, à parte das tentativas.

        A chamada fica registrada mesmo quando o provedor devolve erro, para que
        uma indisponibilidade seja auditável sem consumir tentativa do documento.
        """
        metrics = getattr(self.gemini_extractor, "last_metrics", None) or {}
        attempts = int(metrics.get("api_calls", 0) or 0)
        # Falta de chave é bloqueio local: nada foi enviado ao provedor.
        provider_failed = isinstance(exc, GeminiExtractionError) and exc.error_code != "missing_api_key"
        if not attempts and not provider_failed:
            return []
        document.api_attempt_count += attempts
        if provider_failed:
            document.provider_failure_count += 1
        return ["api_attempt_count", "provider_failure_count"]

    @staticmethod
    def _failure_message(exc):
        if isinstance(exc, GeminiExtractionError):
            return exc.user_message
        if isinstance(exc, (PreflightError, DocumentQualityError)):
            return str(exc)
        return "Falha interna ao processar o documento. Tente novamente ou solicite suporte."

    @staticmethod
    def _claim(document):
        """Marca o documento como PROCESSING de forma atômica.

        Um UPDATE condicional garante que apenas uma submissão assuma o
        documento: submissões concorrentes não atualizam nenhuma linha e são
        recusadas antes de iniciar qualquer extração. Um processamento
        interrompido deixa o registro preso em PROCESSING, por isso ele pode ser
        reivindicado novamente depois de PROCESSING_STALE_AFTER.
        """
        now = timezone.now()
        claimed = (
            Document.objects.filter(pk=document.pk)
            .exclude(status=Document.Status.PROCESSING, updated_at__gt=now - PROCESSING_STALE_AFTER)
            .update(status=Document.Status.PROCESSING, error_message="", updated_at=now)
        )
        if not claimed:
            raise ProcessingInProgress()
        document.status = Document.Status.PROCESSING
        document.error_message = ""
        document.updated_at = now

    def _extract(self, document, *, paid_confirmed):
        template_key = "generic"
        if document.template_id:
            template_key = f"{document.template.code}:{document.template.version}"
        cache_key = hashlib.sha256(f"{document.sha256}:{settings.GEMINI_MODEL}:{PROMPT_VERSION}:{LAYOUT_CACHE_VERSION}:{template_key}".encode()).hexdigest()
        cached = ExtractionCache.objects.filter(cache_key=cache_key).first()
        if cached:
            return cached.payload, cached.token_count, cached.source, {
                "input_tokens": cached.input_token_count,
                "output_tokens": cached.output_token_count,
                "api_calls": 0,
                # O consumo veio da chamada original já contabilizada.
                "usage_reported": cached.source == "local" or cached.token_count > 0,
            }

        if document.mime_type == "application/pdf" and not document.template_id:
            pages = extract_pdf_tables(document.file.path)
            if any(page["tables"] for page in pages):
                payload = {"document_name": document.original_name, "pages": pages, "alerts": []}
                self._cache(cache_key, document, payload, 0, "local", {"input_tokens": 0, "output_tokens": 0, "api_calls": 0})
                return payload, 0, "local", {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

        # Daqui para baixo a extração exige uma chamada paga: cache e leitura
        # local já foram descartados, então todas as pré-condições da IA são
        # verificadas antes de tocar no arquivo ou na rede.
        self._ensure_ai_allowed(document, paid_confirmed=paid_confirmed)
        data, mime_type = self._prepare_input(document)
        payload, token_count = self.gemini_extractor.extract(
            data=data,
            mime_type=mime_type,
            document_name=document.original_name,
            template=document.template if document.template_id else None,
        )
        metrics = getattr(self.gemini_extractor, "last_metrics", {"input_tokens": token_count, "output_tokens": 0, "api_calls": 1})
        self._cache(cache_key, document, payload, token_count, "gemini", metrics)
        return payload, token_count, "gemini", metrics

    def _prepare_input(self, document):
        data = document.file.read()
        document.file.seek(0)
        if not document.is_image:
            return data, document.mime_type
        processed = preprocess_image(data, document.mime_type)
        document.quality_score = processed.quality_score
        document.quality_warnings = processed.warnings
        document.save(update_fields=["quality_score", "quality_warnings", "updated_at"])
        if processed.quality_score < 0.08:
            raise DocumentQualityError("A qualidade da fotografia é insuficiente para leitura segura. Envie uma foto mais nítida e bem iluminada.")
        if not document.preprocessed_file:
            document.preprocessed_file.save(f"{document.pk}-preprocessado.png", ContentFile(processed.data), save=False)
        document.save(update_fields=["preprocessed_file", "quality_score", "quality_warnings", "updated_at"])
        self._create_region_previews(document, processed.data)
        return processed.data, processed.mime_type

    @staticmethod
    def _create_region_previews(document, processed_data):
        if not document.template_id:
            return
        from modelos.models import FieldRegionPreview

        for field in document.template.fields.exclude(region=None):
            preview_data = crop_region(processed_data, field.region)
            preview, _ = FieldRegionPreview.objects.get_or_create(document=document, field=field)
            preview.image.save(f"{document.pk}-{field.field_id}.png", ContentFile(preview_data), save=True)

    def _cache(self, cache_key, document, payload, token_count, source, metrics):
        ExtractionCache.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                "sha256": document.sha256,
                "model": settings.GEMINI_MODEL if source == "gemini" else "local",
                "prompt_version": PROMPT_VERSION,
                "payload": payload,
                "token_count": token_count,
                "input_token_count": metrics.get("input_tokens", 0),
                "output_token_count": metrics.get("output_tokens", 0),
                "api_call_count": metrics.get("api_calls", 0),
                "source": source,
            },
        )

    @staticmethod
    def estimate_cost(token_count):
        return (Decimal(token_count) / Decimal(1_000_000)) * Decimal("0.10")

    def _ai_configured(self):
        """Pergunta ao extractor se ele tem credencial.

        Um extractor injetado (testes, implementação alternativa) que não
        expõe is_configured() é considerado pronto: a credencial é
        responsabilidade de quem o injetou.
        """
        checker = getattr(self.gemini_extractor, "is_configured", None)
        return checker() if callable(checker) else True

    def _ensure_ai_allowed(self, document, *, paid_confirmed):
        """Valida as pré-condições da chamada paga, sem consumir tentativa."""
        if document.attempts_exhausted:
            raise AttemptsExhausted()
        if not paid_confirmed:
            raise AIConfirmationRequired()
        if not self._ai_configured():
            raise AINotConfigured()
        self._ensure_budget(document)

    @staticmethod
    def _ensure_budget(document):
        month_documents = Document.objects.filter(
            user=document.user,
            created_at__year=document.created_at.year,
            created_at__month=document.created_at.month,
        )
        month_total = month_documents.aggregate(total=Sum("estimated_cost_usd"))["total"] or Decimal("0")
        if month_total >= Decimal(str(settings.MAX_MONTHLY_ESTIMATED_USD)):
            raise BudgetExceeded("O limite mensal estimado foi atingido; ajuste MAX_MONTHLY_ESTIMATED_USD antes de continuar.")
        month_calls = month_documents.aggregate(total=Sum("api_call_count"))["total"] or 0
        if month_calls >= settings.MAX_MONTHLY_API_CALLS:
            raise BudgetExceeded("O limite mensal de chamadas Gemini foi atingido; ajuste MAX_MONTHLY_API_CALLS antes de continuar.")
