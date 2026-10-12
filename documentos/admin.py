from django.contrib import admin

from .models import Document, ExtractionCache


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ("original_name", "user", "status", "page_count", "created_at")
    search_fields = ("original_name", "sha256", "user__username")


@admin.register(ExtractionCache)
class ExtractionCacheAdmin(admin.ModelAdmin):
    list_display = ("sha256", "model", "source", "created_at")
