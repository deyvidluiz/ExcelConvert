import hashlib
from decimal import Decimal

from django.conf import settings
from django.core.files.base import ContentFile
from django.db.models import Sum
from django.utils import timezone

from documentos.models import Document, ExtractionCache
from validacao.services import validate_payload

from .gemini_service import GeminiExtractor
from .local_pdf import extract_pdf_tables
from .preprocessamento import crop_region, preprocess_image
from .prompts import PROMPT_VERSION


class DocumentQualityError(RuntimeError):
    pass


class ExtractionService:
    def __init__(self, gemini_extractor=None):
        self.gemini_extractor = gemini_extractor or GeminiExtractor()

    def process(self, document: Document, *, paid_confirmed=False):
        document.status = Document.Status.PROCESSING
        document.error_message = ""
        document.save(update_fields=["status", "error_message", "updated_at"])
        try:
            payload, token_count, source, metrics = self._extract(document, paid_confirmed=paid_confirmed)
            payload["alerts"] = list(dict.fromkeys(payload.get("alerts", []) + validate_payload(payload)))
            document.extraction_payload = payload
            document.model = settings.GEMINI_MODEL if source == "gemini" else "local"
            document.token_count = token_count
            document.input_token_count = metrics.get("input_tokens", 0)
            document.output_token_count = metrics.get("output_tokens", 0)
            document.api_call_count = metrics.get("api_calls", 0)
            document.pages_processed = document.page_count
            document.estimated_cost_usd = self.estimate_cost(token_count) if source == "gemini" else Decimal("0")
            document.estimated_cost_brl = document.estimated_cost_usd * Decimal(str(settings.USD_TO_BRL))
            document.status = Document.Status.READY
            document.processed_at = timezone.now()
            document.save(update_fields=["model", "token_count", "input_token_count", "output_token_count", "api_call_count", "pages_processed", "estimated_cost_usd", "estimated_cost_brl", "extraction_payload", "status", "processed_at", "updated_at"])
            return payload
        except Exception as exc:
            document.status = Document.Status.FAILED
            document.error_message = str(exc)
            document.retry_count += 1
            document.save(update_fields=["status", "error_message", "retry_count", "updated_at"])
            raise

    def _extract(self, document, *, paid_confirmed):
        template_key = "generic"
        if document.template_id:
            template_key = f"{document.template.code}:{document.template.version}"
        cache_key = hashlib.sha256(f"{document.sha256}:{settings.GEMINI_MODEL}:{PROMPT_VERSION}:{template_key}".encode()).hexdigest()
        cached = ExtractionCache.objects.filter(cache_key=cache_key).first()
        if cached:
            return cached.payload, cached.token_count, cached.source, {
                "input_tokens": cached.input_token_count,
                "output_tokens": cached.output_token_count,
                "api_calls": cached.api_call_count,
            }

        if document.mime_type == "application/pdf" and not document.template_id:
            pages = extract_pdf_tables(document.file.path)
            if any(page["tables"] for page in pages):
                payload = {"document_name": document.original_name, "pages": pages, "alerts": []}
                self._cache(cache_key, document, payload, 0, "local", {"input_tokens": 0, "output_tokens": 0, "api_calls": 0})
                return payload, 0, "local", {"input_tokens": 0, "output_tokens": 0, "api_calls": 0}

        if not paid_confirmed:
            raise RuntimeError("Este documento precisa de IA para ser processado. Marque a confirmação de custo e tente novamente.")
        if document.retry_count >= 3:
            raise RuntimeError("Limite de tentativas atingido. Revise o arquivo ou solicite suporte.")
        self._ensure_budget(document)
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

    @staticmethod
    def _ensure_budget(document):
        month_total = Document.objects.filter(
            user=document.user,
            created_at__year=document.created_at.year,
            created_at__month=document.created_at.month,
        ).aggregate(total=Sum("estimated_cost_usd"))["total"] or Decimal("0")
        if month_total >= Decimal(str(settings.MAX_MONTHLY_ESTIMATED_USD)):
            raise RuntimeError("O limite mensal estimado foi atingido; ajuste MAX_MONTHLY_ESTIMATED_USD antes de continuar.")
