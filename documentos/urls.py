from django.urls import path

from . import views

app_name = "documentos"
urlpatterns = [
    path("upload/", views.upload, name="upload"),
    path("<uuid:pk>/processar/", views.process_document, name="process"),
    path("<uuid:pk>/arquivo/", views.serve_document, name="file"),
    path("<uuid:pk>/campo/<slug:field_id>/preview/", views.serve_field_preview, name="field-preview"),
    path("<uuid:pk>/excluir/", views.delete_document, name="delete"),
]
