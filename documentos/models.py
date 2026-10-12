import uuid

from django.conf import settings
from django.db import models


class Document(models.Model):
    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Aguardando processamento"
        PROCESSING = "processing", "Processando"
        READY = "ready", "Pronto para revisão"
        FAILED = "failed", "Falhou"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="documents")
    file = models.FileField(upload_to="documents/%Y/%m/%d/")
    original_name = models.CharField(max_length=255)
    mime_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField(default=0)
    sha256 = models.CharField(max_length=64, db_index=True)
    page_count = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.UPLOADED)
    error_message = models.TextField(blank=True)
    retry_count = models.PositiveIntegerField(default=0)
    model = models.CharField(max_length=120, blank=True)
    token_count = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    estimated_cost_brl = models.DecimalField(max_digits=12, decimal_places=4, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "status"]), models.Index(fields=["user", "created_at"])]

    def __str__(self):
        return self.original_name

    @property
    def is_image(self):
        return self.mime_type.startswith("image/")


class ExtractionCache(models.Model):
    cache_key = models.CharField(max_length=128, unique=True)
    sha256 = models.CharField(max_length=64, db_index=True)
    model = models.CharField(max_length=120)
    prompt_version = models.CharField(max_length=50)
    payload = models.JSONField()
    token_count = models.PositiveIntegerField(default=0)
    source = models.CharField(max_length=20, default="gemini")
    created_at = models.DateTimeField(auto_now_add=True)

