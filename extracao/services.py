import hashlib
from decimal import Decimal
from django.db.models import Sum

from django.conf import settings
from django.utils import timezone

from documentos.models import Document, ExtractionCache
from validacao.services import validate_payload

from .gemini_service import GeminiExtractor
from .local_pdf import extract_pdf_tables
from .prompts import PROMPT_VERSION


class ExtractionService:
    def __init__(self, gemini_extractor=None):
        self.gemini_extractor = gemini_extractor or GeminiExtractor()

    def process(self, document: Document, *, paid_confirmed=False):
        document.status = Document.Status.PROCESSING
        document.error_message = ""
        document.save(update_fields=["status", "error_message", "updated_at"])
        try:
            payload, token_count, source = self._extract(document, paid_confirmed=paid_confirmed)
            payload["alerts"] = list(dict.fromkeys(payload.get("alerts", []) + validate_payload(payload)))
            document.model = settings.GEMINI_MODEL if source == "gemini" else "local"
            document.token_count = token_count
            document.estimated_cost_usd = self.estimate_cost(token_count) if source == "gemini" else Decimal("0")
            document.estimated_cost_brl = document.estimated_cost_usd * Decimal(str(settings.USD_TO_BRL))
            document.status = Document.Status.READY
            document.processed_at = timezone.now()
            document.save(update_fields=["model", "token_count", "estimated_cost_usd", "estimated_cost_brl", "status", "processed_at", "updated_at"])
            return payload
        except Exception as exc:
            document.status = Document.Status.FAILED
            document.error_message = str(exc)
            document.retry_count += 1
            document.save(update_fields=["status", "error_message", "retry_count", "updated_at"])
            raise

    def _extract(self, document, *, paid_confirmed):
        cache_key = hashlib.sha256(f"{document.sha256}:{settings.GEMINI_MODEL}:{PROMPT_VERSION}".encode()).hexdigest()
        cached = ExtractionCache.objects.filter(cache_key=cache_key).first()
        if cached:
            return cached.payload, cached.token_count, cached.source
        if document.mime_type == "application/pdf":
            pages = extract_pdf_tables(document.file.path)
            if any(page["tables"] for page in pages):
                payload = {"document_name": document.original_name, "pages": pages, "alerts": []}
                self._cache(cache_key, document, payload, 0, "local")
                return payload, 0, "local"
        if not paid_confirmed:
            raise RuntimeError("Este documento precisa de IA para ser processado. Marque a confirmação de custo e tente novamente.")
        if document.retry_count >= 3:
            raise RuntimeError("Limite de tentativas atingido. Revise o arquivo ou solicite suporte.")
        self._ensure_budget(document)
        data = document.file.read()
        document.file.seek(0)
        payload, token_count = self.gemini_extractor.extract(data=data, mime_type=document.mime_type, document_name=document.original_name)
        self._cache(cache_key, document, payload, token_count, "gemini")
        return payload, token_count, "gemini"

    def _cache(self, cache_key, document, payload, token_count, source):
        ExtractionCache.objects.update_or_create(
            cache_key=cache_key,
            defaults={
                "sha256": document.sha256,
                "model": settings.GEMINI_MODEL if source == "gemini" else "local",
                "prompt_version": PROMPT_VERSION,
                "payload": payload,
                "token_count": token_count,
                "source": source,
            },
        )

    @staticmethod
    def estimate_cost(token_count):
        price_per_million = Decimal("0.10")
        return (Decimal(token_count) / Decimal(1_000_000)) * price_per_million

    @staticmethod
    def _ensure_budget(document):
        month_total = Document.objects.filter(
            user=document.user,
            created_at__year=document.created_at.year,
            created_at__month=document.created_at.month,
        ).aggregate(total=Sum("estimated_cost_usd"))["total"] or Decimal("0")
        if month_total >= Decimal(str(settings.MAX_MONTHLY_ESTIMATED_USD)):
            raise RuntimeError("O limite mensal estimado foi atingido; ajuste MAX_MONTHLY_ESTIMATED_USD antes de continuar.")
