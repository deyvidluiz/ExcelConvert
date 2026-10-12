from django.urls import path

from . import views

app_name = "documentos"
urlpatterns = [
    path("upload/", views.upload, name="upload"),
    path("<uuid:pk>/processar/", views.process_document, name="process"),
    path("<uuid:pk>/arquivo/", views.serve_document, name="file"),
    path("<uuid:pk>/excluir/", views.delete_document, name="delete"),
]
