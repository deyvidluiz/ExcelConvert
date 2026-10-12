from django.contrib import admin

from .models import DocumentTemplate, EvaluationField, EvaluationRun, ExcelFieldMapping, ExcelTemplate, FieldRegionPreview, ReferenceValue, TemplateField


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "version", "issuer", "calibration_status", "is_active")
    search_fields = ("name", "code", "issuer")
    list_filter = ("is_active", "calibration_status")


@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    list_display = ("field_id", "name", "section", "page_number", "expected_type", "required")
    list_filter = ("expected_type", "required", "handwritten_priority")
    search_fields = ("field_id", "name", "section")


@admin.register(ExcelTemplate)
class ExcelTemplateAdmin(admin.ModelAdmin):
    list_display = ("name", "document_template", "version", "is_active")


admin.site.register(ExcelFieldMapping)
admin.site.register(ReferenceValue)
admin.site.register(EvaluationRun)
admin.site.register(EvaluationField)
admin.site.register(FieldRegionPreview)
