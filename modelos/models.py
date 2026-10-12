import uuid

from django.conf import settings
from django.db import models


class DocumentTemplate(models.Model):
    """Modelo versionado da ficha física, independente de uma conversão."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.SlugField(max_length=100)
    name = models.CharField(max_length=180)
    issuer = models.CharField(max_length=120, blank=True)
    version = models.CharField(max_length=30, default="1.0.0")
    description = models.TextField(blank=True)
    page_count = models.PositiveIntegerField(default=1)
    repeat_layout_per_page = models.BooleanField(
        default=False,
        help_text="Quando ativo, o catálogo de campos se repete em cada página do documento.",
    )
    reference_pdf = models.FileField(upload_to="template_references/%Y/%m/%d/", blank=True)
    reference_sha256 = models.CharField(max_length=64, blank=True)
    calibration_status = models.CharField(max_length=30, default="pending")
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["code", "-version"]
        constraints = [models.UniqueConstraint(fields=["code", "version"], name="unique_document_template_version")]

    def __str__(self):
        return f"{self.name} v{self.version}"

    @property
    def schema_for_prompt(self):
        return [field.schema_for_prompt for field in self.fields.order_by("page_number", "order", "field_id")]


class TemplateField(models.Model):
    class ExpectedType(models.TextChoices):
        TEXT = "text", "Texto"
        NUMBER = "number", "Número"
        DECIMAL = "decimal", "Decimal"
        DATE = "date", "Data"
        BOOLEAN = "boolean", "Sim/não"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name="fields")
    field_id = models.SlugField(max_length=100)
    name = models.CharField(max_length=160)
    section = models.CharField(max_length=160)
    page_number = models.PositiveIntegerField()
    order = models.PositiveIntegerField(default=0)
    location_hint = models.CharField(max_length=220, blank=True)
    region = models.JSONField(null=True, blank=True, help_text="Coordenadas normalizadas x/y/width/height; nulo até calibração.")
    excel_sheet = models.CharField(max_length=80, blank=True)
    excel_cell = models.CharField(max_length=40, blank=True)
    excel_range = models.CharField(max_length=80, blank=True)
    expected_type = models.CharField(max_length=20, choices=ExpectedType.choices, default=ExpectedType.TEXT)
    validation_rule = models.CharField(max_length=220, blank=True)
    required = models.BooleanField(default=False)
    handwritten_priority = models.BooleanField(default=True)

    class Meta:
        ordering = ["page_number", "order", "field_id"]
        constraints = [models.UniqueConstraint(fields=["template", "field_id"], name="unique_template_field_id")]

    def __str__(self):
        return f"{self.template.code}:{self.field_id}"

    @property
    def schema_for_prompt(self):
        schema = {
            "id": self.field_id,
            "label": self.name,
            "section": self.section,
            "page": self.page_number,
            "anchor": self.location_hint,
            "type": self.expected_type,
            "required": self.required,
        }
        if self.region:
            schema["region"] = self.region
        return schema


class ExcelTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name="excel_templates")
    name = models.CharField(max_length=180)
    version = models.CharField(max_length=30, default="1.0.0")
    workbook = models.FileField(upload_to="excel_templates/%Y/%m/%d/")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document_template", "name", "version"], name="unique_excel_template_version")]

    def __str__(self):
        return f"{self.name} v{self.version}"


class ExcelFieldMapping(models.Model):
    excel_template = models.ForeignKey(ExcelTemplate, on_delete=models.CASCADE, related_name="mappings")
    field = models.ForeignKey(TemplateField, on_delete=models.CASCADE, related_name="excel_mappings")
    sheet_name = models.CharField(max_length=80)
    cell_or_range = models.CharField(max_length=80)
    expected_type = models.CharField(max_length=20, choices=TemplateField.ExpectedType.choices, default=TemplateField.ExpectedType.TEXT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["excel_template", "field"], name="unique_excel_field_mapping")]


class ReferenceValue(models.Model):
    """Valor revisado por uma pessoa para avaliação, nunca gerado automaticamente."""

    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name="reference_values")
    field = models.ForeignKey(TemplateField, on_delete=models.CASCADE, related_name="reference_values")
    source_document = models.CharField(max_length=255)
    page_number = models.PositiveIntegerField()
    value = models.TextField(null=True, blank=True)
    notes = models.TextField(blank=True)
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["template", "field", "source_document"], name="unique_reference_value")]


class EvaluationRun(models.Model):
    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name="evaluation_runs")
    document = models.ForeignKey("documentos.Document", null=True, blank=True, on_delete=models.SET_NULL, related_name="evaluations")
    created_at = models.DateTimeField(auto_now_add=True)
    fields_identified = models.PositiveIntegerField(default=0)
    fields_correct = models.PositiveIntegerField(default=0)
    numeric_errors = models.PositiveIntegerField(default=0)
    unreadable_fields = models.PositiveIntegerField(default=0)
    positioning_errors = models.PositiveIntegerField(default=0)
    input_tokens = models.PositiveIntegerField(default=0)
    output_tokens = models.PositiveIntegerField(default=0)
    estimated_cost_usd = models.DecimalField(max_digits=12, decimal_places=8, default=0)


class EvaluationField(models.Model):
    run = models.ForeignKey(EvaluationRun, on_delete=models.CASCADE, related_name="fields")
    field = models.ForeignKey(TemplateField, on_delete=models.CASCADE)
    page_number = models.PositiveIntegerField()
    predicted_value = models.TextField(null=True, blank=True)
    reference_value = models.TextField(null=True, blank=True)
    is_correct = models.BooleanField(null=True)
    is_unreadable = models.BooleanField(default=False)
    numeric_error = models.BooleanField(default=False)
    positioning_error = models.BooleanField(default=False)


class FieldRegionPreview(models.Model):
    document = models.ForeignKey("documentos.Document", on_delete=models.CASCADE, related_name="field_previews")
    field = models.ForeignKey(TemplateField, on_delete=models.CASCADE, related_name="document_previews")
    image = models.FileField(upload_to="field_previews/%Y/%m/%d/")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["document", "field"], name="unique_document_field_preview")]
